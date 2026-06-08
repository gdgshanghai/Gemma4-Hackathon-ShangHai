import { apiClient as axios } from './base'

export async function getPsychLatest() {
  return (await axios.get('/api/psych/latest')).data
}

export async function getPsychHistory(limit = 100) {
  return (await axios.get('/api/psych/history', { params: { limit } })).data
}

export async function updatePsychConfig(payload) {
  return (await axios.post('/api/psych/config', payload)).data
}
