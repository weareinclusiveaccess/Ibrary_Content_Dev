from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from typing import Literal, Optional,List, Dict, Any


@dataclass
class SubtopicNotes:
    subtopic_number: int
    subtopic_title: str
    subtopic_content: str
    images: List[str]
    tables: List[str]

@dataclass
class WeekNotes:
    week_number: int
    week_topic: str
    subtopics: List[SubtopicNotes]
    images: List[str]
    tables: List[str]


class Notes(BaseModel):
    subject: str
    class: str
    term: int
    weeks: List[Week]