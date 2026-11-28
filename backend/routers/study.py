"""本地资料库的 HTTP 入口。"""

from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from models.study import (
    ConversationInput, CourseInput, CourseOrder, Identifier, ScopeKind,
    StudyAnalysisRequest, StudyArchiveInput, StudyQuestion, StudyRetry, StudyTaskKind,
    VideoGroupInput, VideoLibraryUpdate, WikiLinkInput, WikiPageInput,
)
from services.study import StudyService
from services.ai_client import AIServiceError
from storage.study_db import StudyProblem


class StudyRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request):
            try:
                response = await handler(request)
            except StudyProblem as error:
                response = JSONResponse({"detail": error.detail, "code": error.code}, status_code=error.status)
            except AIServiceError as error:
                response = JSONResponse({"detail": str(error), "code": error.code}, status_code=error.status_code)
            except RequestValidationError:
                response = JSONResponse(
                    {"detail": "请求参数格式无效", "code": "invalid_request"}, status_code=422,
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        return handle


router = APIRouter(prefix="/api/study", tags=["study"], route_class=StudyRoute)


async def get_study(request: Request) -> StudyService:
    runtime = request.app.state.study
    if runtime is None:
        raise StudyProblem("资料库暂不可用", 503, "study_unavailable")
    return runtime.for_user(request.state.user.id)


@router.get("/status")
async def study_status(service: StudyService = Depends(get_study)):
    return service.status()


@router.get("/library")
async def read_library(service: StudyService = Depends(get_study)):
    return service.list_library()


@router.get("/videos/{video_id}")
async def read_video(video_id: Identifier, service: StudyService = Depends(get_study)):
    return service.video(video_id)


@router.patch("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def update_video(video_id: Identifier, body: VideoLibraryUpdate, service: StudyService = Depends(get_study)):
    service.update_video(video_id, body.group_id, body.title)
    return Response(status_code=204)


@router.get("/videos/{video_id}/impact")
async def read_video_impact(video_id: Identifier, service: StudyService = Depends(get_study)):
    return service.video_impact(video_id)


@router.delete("/videos/{video_id}")
async def delete_video(video_id: Identifier, clear_turns: bool = False, service: StudyService = Depends(get_study)):
    return service.delete_video(video_id, clear_turns)


@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def add_group(body: VideoGroupInput, service: StudyService = Depends(get_study)):
    return service.save_group(body.title)


@router.patch("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rename_group(group_id: Identifier, body: VideoGroupInput, service: StudyService = Depends(get_study)):
    service.save_group(body.title, group_id)
    return Response(status_code=204)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: Identifier, service: StudyService = Depends(get_study)):
    service.delete_group(group_id)
    return Response(status_code=204)


@router.post("/courses", status_code=status.HTTP_201_CREATED)
async def add_course(body: CourseInput, service: StudyService = Depends(get_study)):
    return service.create_course(body.title)


@router.get("/courses/{course_id}")
async def read_course(course_id: Identifier, include_suggestions: bool = True,
                      service: StudyService = Depends(get_study)):
    return await service.course(course_id, include_suggestions=include_suggestions)


@router.patch("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rename_course(course_id: Identifier, body: CourseInput, service: StudyService = Depends(get_study)):
    service.rename_course(course_id, body.title)
    return Response(status_code=204)


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(course_id: Identifier, service: StudyService = Depends(get_study)):
    service.delete_course(course_id)
    return Response(status_code=204)


@router.put("/courses/{course_id}/videos/{video_id}")
async def add_course_video(course_id: Identifier, video_id: Identifier, service: StudyService = Depends(get_study)):
    return service.add_video(course_id, video_id)


@router.delete("/courses/{course_id}/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_course_video(course_id: Identifier, video_id: Identifier, service: StudyService = Depends(get_study)):
    service.remove_video(course_id, video_id)
    return Response(status_code=204)


@router.put("/courses/{course_id}/order", status_code=status.HTTP_204_NO_CONTENT)
async def save_course_order(course_id: Identifier, body: CourseOrder, service: StudyService = Depends(get_study)):
    service.reorder(course_id, body.video_ids)
    return Response(status_code=204)


@router.get("/wiki/{page_id}")
async def read_page(page_id: Identifier, service: StudyService = Depends(get_study)):
    return service.wiki_page(page_id)


@router.patch("/wiki/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def edit_page(page_id: Identifier, body: WikiPageInput, service: StudyService = Depends(get_study)):
    service.edit_page(page_id, body.title, body.aliases)
    return Response(status_code=204)


@router.post("/wiki/{page_id}/merge/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def merge_pages(page_id: Identifier, target_id: Identifier, service: StudyService = Depends(get_study)):
    service.merge_pages(page_id, target_id)
    return Response(status_code=204)


@router.put("/wiki/{page_id}/links/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def edit_link(page_id: Identifier, target_id: Identifier, body: WikiLinkInput,
                    service: StudyService = Depends(get_study)):
    service.link_pages(page_id, target_id, body.accepted)
    return Response(status_code=204)


@router.get("/conversations")
async def read_conversations(scope: Optional[ScopeKind] = None, scope_id: Optional[Identifier] = None,
                             service: StudyService = Depends(get_study)):
    if scope and (scope == "library") != (scope_id is None):
        raise StudyProblem("请选择对应的视频或课程")
    return service.list_conversations(scope, scope_id)


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def new_conversation(body: ConversationInput, service: StudyService = Depends(get_study)):
    return service.create_conversation(body.scope, body.scope_id)


@router.get("/conversations/{conversation_id}")
async def read_conversation(conversation_id: Identifier, service: StudyService = Depends(get_study)):
    return service.conversation(conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: Identifier, service: StudyService = Depends(get_study)):
    service.delete_conversation(conversation_id)
    return Response(status_code=204)


@router.post("/conversations/{conversation_id}/questions", status_code=status.HTTP_202_ACCEPTED)
async def submit_question(conversation_id: Identifier, body: StudyQuestion, service: StudyService = Depends(get_study)):
    return service.submit_question(conversation_id, body).brief()


@router.post("/analysis", status_code=status.HTTP_202_ACCEPTED)
async def submit_analysis(body: StudyAnalysisRequest, service: StudyService = Depends(get_study)):
    return service.submit_analysis(body).brief()


@router.put("/analysis/{task_id}/archive")
async def archive_analysis(task_id: Identifier, body: StudyArchiveInput, service: StudyService = Depends(get_study)):
    return service.archive_analysis(task_id, private_consent=body.private_consent)


@router.delete("/analysis/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(task_id: Identifier, service: StudyService = Depends(get_study)):
    service.jobs.delete_analysis(task_id)
    return Response(status_code=204)


@router.get("/tasks")
async def read_tasks(kind: Optional[StudyTaskKind] = None, service: StudyService = Depends(get_study)):
    return [job.brief() for job in service.jobs.list(kind=kind)]


@router.get("/tasks/{task_id}")
async def read_task(task_id: Identifier, service: StudyService = Depends(get_study)):
    return service.task(task_id)


@router.post("/tasks/{task_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_task(task_id: Identifier, body: StudyRetry, service: StudyService = Depends(get_study)):
    return service.retry_task(task_id, body).brief()


@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: Identifier, service: StudyService = Depends(get_study)):
    return service.jobs.cancel(service.jobs.get(task_id)).brief()
