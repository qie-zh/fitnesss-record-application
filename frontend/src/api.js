import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

export const suggestExercise = (q) => http.get('/suggest/exercise', { params: { q } })
export const getRecentWorkouts = () => http.get('/workouts/recent')
export const getByMuscle = (group) => http.get('/workouts/by-muscle', { params: { group } })
export const getTrend = (exercise) => http.get('/workouts/trend', { params: { exercise } })
export const createWorkout = (data) => http.post('/workouts', data)
export const updateWorkout = (id, data) => http.put(`/workouts/${id}`, data)
export const deleteWorkout = (id) => http.delete(`/workouts/${id}`)

export const getChatSessions = () => http.get('/chat/sessions')
export const getChatMessages = (sessionId) => http.get(`/chat/sessions/${sessionId}/messages`)
export const deleteChatSession = (sessionId) => http.delete(`/chat/sessions/${sessionId}`)
export const sendChat = (data) => http.post('/chat', data)
