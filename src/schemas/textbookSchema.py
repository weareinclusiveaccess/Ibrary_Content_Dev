

from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from typing import Literal, Optional,List, Dict, Any


@dataclass
class TextbookChapterSubsubtopic:
    subsubtopic_title: str | None = None
    subsubtopic_start_page: int | None = None
    subsubtopic_end_page: int | None = None
    subsubtopic_notes: List[str] = Field(default=[], description="List of notes for the subsubtopic")
    subsubtopic_page_contents: str | None = None
    subsubtopic_connections: List[str] = Field(default=[], description="List of connections of the subsubtopic to other real-world applications")

@dataclass
class TextbookChapterSubtopic:
    subtopic_number: int | None = None
    subtopic_title: str | None = None
    subtopic_page_label: str | None = None
    subtopic_learning_outcomes: List[str]= Field(default=[], description="List of learning outcomes for the subtopic")
    subtopic_assessments: List[str]= Field(default=[], description="List of assessments for the subtopic")
    subtopic_concept: str | None = None
    subtopic_summary: str | None = None
    subtopic_subsubtopics: List[TextbookSubsubtopic]= Field(default=[], description="List of subsubtopics for the subtopic")

@dataclass
class TextbookChapterTable:
    table_number: int | None = None
    table_title: str | None = None
    table_contents: List[Dict[str, Any]]= Field(default=[], description="List of contents for the table")

@dataclass
class TextbookChapterFigure:
    figure_number: int | None = None
    figure_title: str | None = None
    figure_description: str | None = None
    figure_image_url: str | None = None
    

@dataclass
class TextbookChapterExercise:
    question_number: int | None = None
    question_type: Literal["multiple_choice", "fill_in_the_blank", "short_answer", "essay"] | None = None
    question: str | None = None
    answer_options: Optional[Dict[str, str]] = Field(default={}, description="List of answer options for the question")
    correct_answer: Optional[str]
    explanation: Optional[str]
    difficulty: Literal["easy", "medium", "hard"] = "easy"

@dataclass
class TextbookQuestionArtefact:
    artifact_type: Literal["image", "video", "audio", "text"]
    artifact_url: str
    artifact_description: str

@dataclass
class TextbookCriticalThinkingQuestion:
    question_number: int
    question: str
    question_artefacts: Optional[List[TextbookQuestionArtefact]] = Field(default=[], description="List of artifacts for the question")
    correct_answer: Optional[str]
    difficulty: Literal["easy", "medium", "hard"] = "hard"

@dataclass
class TextbookChapterExercises:
    chapter_exercises: List[TextbookExercise] = Field(default=[], description="List of exercises for the chapter")
    chapter_critical_thinking_questions: List[TextbookCriticalThinkingQuestion] = Field(default=[], description="List of critical thinking questions for the chapter")

@dataclass
class TextbookChapter:
    chapter_number: int | None = None
    chapter_title: str | None = None
    chapter_page_label: str | None = None
    chapter_outline: str | None = None
    chapter_prerequisites: str | None = None
    chapter_introduction: str
    chapter_summary: str | None = None
    chapter_subtopics: List[TextbookSubtopic]= Field(default=[], description="List of subtopics for the chapter")
    chapter_tables: List[TextbookTable]= Field(default=[], description="List of tables for the chapter")
    chapter_figures: List[TextbookFigure]= Field(default=[], description="List of figures for the chapter")
    chapter_exercises: Optional[TextbookChapterExercises] = Field(default=None, description="Exercises for the chapter")
    chapter_metadata: List[Dict[str, Any]]= Field(default=[], description="List of metadata for the chapter")
   
@dataclass
class Textbook:
    textbook_name: str
    textbook_author: str
    textbook_publisher: Optional[str] = None
    textbook_year: Optional[int] = None
    textbook_edition: Optional[str] = None
    textbook_isbn: Optional[str] = None
    textbook_pages: int
    textbook_chapters: List[TextbookChapter]= Field(default=[], description="List of chapters for the textbook")