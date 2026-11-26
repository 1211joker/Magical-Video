"""本地资料库请求与模型生成的结构化结果。"""

from typing import Annotated, Literal, Optional
import unicodedata

from pydantic import BaseModel, Field, SecretStr, StringConstraints, model_validator

from models.schemas import ParseRequest

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{32}$")]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
VideoTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
ScopeKind = Literal["video", "course", "library"]
StudyTaskKind = Literal["analysis", "wiki", "question"]


def normalized_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


class CourseInput(BaseModel):
    title: Title


class VideoGroupInput(BaseModel):
    title: Title


class VideoLibraryUpdate(BaseModel):
    group_id: Optional[Identifier]
    title: Optional[VideoTitle] = None


class CourseOrder(BaseModel):
    video_ids: list[Identifier] = Field(max_length=1000)


class StudyAnalysisRequest(ParseRequest):
    url: str = Field(max_length=4096)
    request_id: Identifier
    title: Optional[str] = Field(default=None, max_length=240)
    save: bool = False
    private_consent: bool = False


class StudyRetry(BaseModel):
    bilibili_session: Optional[SecretStr] = None
    panopto_session: Optional[SecretStr] = None
    private_consent: bool = False


class ConversationInput(BaseModel):
    scope: ScopeKind
    scope_id: Optional[Identifier] = None

    @model_validator(mode="after")
    def validate_scope(self):
        if (self.scope == "library") != (self.scope_id is None):
            raise ValueError("请选择对应的视频或课程")
        return self


class StudyQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    request_id: Identifier
    recall: bool = True


class WikiPageInput(BaseModel):
    title: Title
    aliases: list[Title] = Field(default_factory=list, max_length=24)


class WikiLinkInput(BaseModel):
    accepted: bool


class WikiClaimDraft(BaseModel):
    chunk_id: Identifier
    quote: str = Field(min_length=6, max_length=350)
    explanation: str = Field(min_length=3, max_length=600)


class WikiPageDraft(WikiPageInput):
    claims: list[WikiClaimDraft] = Field(min_length=1, max_length=12)
    related: list[Title] = Field(default_factory=list, max_length=6)


class WikiDraft(BaseModel):
    pages: list[WikiPageDraft] = Field(max_length=12)


class StudyAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)
    citations: list[Identifier] = Field(default_factory=list, max_length=8)
    recalled_turns: list[Identifier] = Field(default_factory=list, max_length=3)
    insufficient: bool = False
