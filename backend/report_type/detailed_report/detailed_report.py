import asyncio
from typing import List, Dict, Set, Optional, Any
from fastapi import WebSocket
import gc

from gpt_researcher import GPTResearcher
from gpt_researcher.utils.memory_manager import MemoryManager, research_memory_manager


class DetailedReport:
    def __init__(
        self,
        query: str,
        report_type: str,
        report_source: str,
        source_urls: List[str] = [],
        document_urls: List[str] = [],
        config_path: str = None,
        tone: Any = "",
        websocket: WebSocket = None,
        subtopics: List[Dict] = [],
        headers: Optional[Dict] = None
    ):
        self.query = query
        self.report_type = report_type
        self.report_source = report_source
        self.source_urls = source_urls
        self.document_urls = document_urls
        self.config_path = config_path
        self.tone = tone
        self.websocket = websocket
        self.subtopics = subtopics
        self.headers = headers or {}

        self.gpt_researcher = GPTResearcher(
            query=self.query,
            report_type="research_report",
            report_source=self.report_source,
            source_urls=self.source_urls,
            document_urls=self.document_urls,
            config_path=self.config_path,
            tone=self.tone,
            websocket=self.websocket,
            headers=self.headers
        )
        self.existing_headers: List[Dict] = []
        self.global_context: List[str] = []
        self.global_written_sections: List[str] = []
        self.global_urls: Set[str] = set(
            self.source_urls) if self.source_urls else set()

    async def run(self) -> str:
        """Run the detailed report generation with memory management."""
        memory_manager = MemoryManager()
        report = None
        
        try:
            async with research_memory_manager(self.gpt_researcher):
                await self._initial_research()
                subtopics = await self._get_all_subtopics()
                initial_memory = memory_manager.get_memory_usage()
                print(f"Memory after initial research: {initial_memory['rss_mb']:.2f} MB")

            report_introduction = await self.gpt_researcher.write_introduction()
            _, report_body = await self._generate_subtopic_reports(subtopics)
            
            # Safe URL update with null check
            if (hasattr(self.gpt_researcher, 'visited_urls') and 
                self.gpt_researcher.visited_urls is not None and 
                hasattr(self, 'global_urls')):
                self.gpt_researcher.visited_urls.update(self.global_urls or set())
            
            report = await self._construct_detailed_report(report_introduction, report_body)
            
            # Clear large strings immediately
            del report_introduction
            del report_body
            del subtopics
            
            return report
            
        finally:
            # Aggressive cleanup phase
            for attr in ['global_context', 'global_urls', 'existing_headers', 
                        'global_written_sections']:
                if hasattr(self, attr):
                    attr_value = getattr(self, attr)
                    if isinstance(attr_value, (list, dict, set)):
                        attr_value.clear()
                    setattr(self, attr, None)
            
            # Clear the researcher object
            if hasattr(self, 'gpt_researcher'):
                for attr in ['context', 'visited_urls', 'intermediate_results']:
                    if hasattr(self.gpt_researcher, attr):
                        setattr(self.gpt_researcher, attr, None)
                self.gpt_researcher = None
            
            # Force cleanup multiple times
            for _ in range(3):
                memory_manager.force_cleanup()
                await asyncio.sleep(0.1)  # Give OS time to reclaim memory

    async def _initial_research(self) -> None:
        await self.gpt_researcher.conduct_research()
        self.global_context = self.gpt_researcher.context
        self.global_urls = self.gpt_researcher.visited_urls

    async def _get_all_subtopics(self) -> List[Dict]:
        subtopics_data = await self.gpt_researcher.get_subtopics()

        all_subtopics = []
        if subtopics_data and subtopics_data.subtopics:
            for subtopic in subtopics_data.subtopics:
                all_subtopics.append({"task": subtopic.task})
        else:
            print(f"Unexpected subtopics data format: {subtopics_data}")

        return all_subtopics

    async def _generate_subtopic_reports(self, subtopics: List[Dict]) -> tuple:
        """Generate reports for subtopics with aggressive memory management."""
        subtopic_reports = []
        subtopics_report_body = ""
        
        for subtopic in subtopics:
            async with research_memory_manager(self.gpt_researcher, check_interval=2):
                result = await self._get_subtopic_report(subtopic)
                if result["report"]:
                    # Store only necessary data
                    subtopic_reports.append({
                        "topic": result["topic"],
                        "report": result["report"]
                    })
                    subtopics_report_body += f"\n\n\n{result['report']}"
                    
                # Clear intermediate data
                if hasattr(self.gpt_researcher, 'context'):
                    self.gpt_researcher.context = []
                MemoryManager.check_memory_threshold()
        
        return subtopic_reports, subtopics_report_body

    async def _get_subtopic_report(self, subtopic: Dict) -> Dict:
        """Get report for a specific subtopic with proper error handling."""
        try:
            current_subtopic_task = subtopic.get('task', '')
            parse_draft_section_titles_text = subtopic.get('section_titles', '')
            
            subtopic_assistant = GPTResearcher(
                query=current_subtopic_task,
                report_type=self.report_type,
                report_source=self.report_source,
                source_urls=self.source_urls,
                document_urls=self.document_urls,
                config_path=self.config_path,
                tone=self.tone,
                websocket=self.websocket
            )

            relevant_contents = await subtopic_assistant.conduct_research()
            subtopic_report = await subtopic_assistant.write_report(
                self.existing_headers,
                relevant_contents,
                self.global_written_sections
            )

            # Safe context handling
            if hasattr(subtopic_assistant, 'context') and subtopic_assistant.context is not None:
                self.global_context = list(set(subtopic_assistant.context))
            else:
                self.global_context = []

            # Safe URL handling
            if hasattr(subtopic_assistant, 'visited_urls'):
                self.global_urls.update(subtopic_assistant.visited_urls or set())

            self.global_written_sections.extend(
                self.gpt_researcher.extract_sections(subtopic_report) or []
            )

            self.existing_headers.append({
                "subtopic task": current_subtopic_task,
                "headers": self.gpt_researcher.extract_headers(subtopic_report) or [],
            })

            # Clear assistant's memory
            if hasattr(subtopic_assistant, 'context'):
                subtopic_assistant.context = None
            if hasattr(subtopic_assistant, 'visited_urls'):
                subtopic_assistant.visited_urls = None

            return {"topic": subtopic, "report": subtopic_report}
            
        except Exception as e:
            print(f"Error in _get_subtopic_report: {str(e)}")
            # Return empty result on error
            return {"topic": subtopic, "report": ""}
        finally:
            # Force garbage collection
            gc.collect()

    async def _construct_detailed_report(self, introduction: str, report_body: str) -> str:
        toc = self.gpt_researcher.table_of_contents(report_body)
        conclusion = await self.gpt_researcher.write_report_conclusion(report_body)
        conclusion_with_references = self.gpt_researcher.add_references(
            conclusion, self.gpt_researcher.visited_urls)
        report = f"{introduction}\n\n{toc}\n\n{report_body}\n\n{conclusion_with_references}"
        return report
