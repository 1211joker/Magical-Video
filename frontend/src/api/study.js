import { apiRequest } from './http.js'
import { videoRequest } from './index.js'

const request = (path, method, data) => apiRequest('/study' + path, method, data)

export const studyApi = {
  status: () => request('/status'),
  library: () => request('/library'),
  video: id => request(`/videos/${id}`),
  updateVideo: (id, groupId, title) => request(`/videos/${id}`, 'PATCH', { group_id: groupId, title }),
  impact: id => request(`/videos/${id}/impact`),
  deleteVideo: (id, clear) => request(`/videos/${id}?clear_turns=${clear}`, 'DELETE'),
  createGroup: title => request('/groups', 'POST', { title }),
  renameGroup: (id, title) => request(`/groups/${id}`, 'PATCH', { title }),
  deleteGroup: id => request(`/groups/${id}`, 'DELETE'),
  course: (id, { includeSuggestions = true } = {}) =>
    request(`/courses/${id}?include_suggestions=${includeSuggestions}`),
  createCourse: title => request('/courses', 'POST', { title }),
  renameCourse: (id, title) => request(`/courses/${id}`, 'PATCH', { title }),
  deleteCourse: id => request(`/courses/${id}`, 'DELETE'),
  addVideo: (courseId, videoId) => request(`/courses/${courseId}/videos/${videoId}`, 'PUT'),
  removeVideo: (courseId, videoId) => request(`/courses/${courseId}/videos/${videoId}`, 'DELETE'),
  order: (id, videoIds) => request(`/courses/${id}/order`, 'PUT', { video_ids: videoIds }),
  wiki: id => request(`/wiki/${id}`),
  editWiki: (id, title, aliases) => request(`/wiki/${id}`, 'PATCH', { title, aliases }),
  mergeWiki: (id, target) => request(`/wiki/${id}/merge/${target}`, 'POST'),
  linkWiki: (id, target, accepted) => request(`/wiki/${id}/links/${target}`, 'PUT', { accepted }),
  tasks: kind => request(kind ? `/tasks?kind=${encodeURIComponent(kind)}` : '/tasks'),
  task: id => request(`/tasks/${id}`),
  archiveAnalysis: (id, privateConsent) => request(`/analysis/${id}/archive`, 'PUT', {
    private_consent: privateConsent,
  }),
  cancelTask: id => request(`/tasks/${id}`, 'DELETE'),
  deleteAnalysis: id => request(`/analysis/${id}`, 'DELETE'),
  retryTask: (id, credentials, consent) => {
    const { bilibiliSession, panoptoSession } = credentials ?? {}
    return request(`/tasks/${id}/retry`, 'POST', {
      bilibili_session: bilibiliSession, panopto_session: panoptoSession, private_consent: consent,
    })
  },
  analyze: (url, credentials, { id, save, consent, title, provider }) => request('/analysis', 'POST', {
    ...videoRequest(url, credentials), request_id: id, save, private_consent: consent, title, provider: provider || undefined,
  }),
  conversations: (scope, scopeId) => {
    const params = new URLSearchParams()
    if (scope) params.set('scope', scope)
    if (scopeId) params.set('scope_id', scopeId)
    return request('/conversations?' + params)
  },
  conversation: id => request(`/conversations/${id}`),
  newConversation: (scope, scopeId) => request('/conversations', 'POST', { scope, scope_id: scopeId }),
  deleteConversation: id => request(`/conversations/${id}`, 'DELETE'),
  ask: (id, question, requestId, recall, provider) => request(`/conversations/${id}/questions`, 'POST', {
    question, request_id: requestId, recall, provider: provider || undefined,
  }),
}

export function studyRequestId() {
  return crypto.randomUUID().replaceAll('-', '')
}
