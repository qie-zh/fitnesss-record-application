import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

export const suggestExercise = (q) => http.get('/suggest/exercise', { params: { q } })
export const getRecentWorkouts = () => http.get('/workouts/recent')
export const getByMuscle = (group) => http.get('/workouts/by-muscle', { params: { group } })
export const getTrend = (exercise) => http.get('/workouts/trend', { params: { exercise } })
export const createWorkout = (data) => http.post('/workouts', data)
