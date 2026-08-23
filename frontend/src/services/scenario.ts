import api from './api'

export const scenarioAPI = {
  parse: (rawText: string) =>
    api.post('/scenarios/parse', { raw_text: rawText }).then(r => r.data.data),
  save: (data: any) =>
    api.post('/scenarios/save', data).then(r => r.data.data),
  defaultScoringRules: () =>
    api.get('/scenarios/default-scoring-rules').then(r => r.data.data),
}

export default scenarioAPI
