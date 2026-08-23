import { Routes, Route } from 'react-router-dom'
import OntologyPage from './OntologyPage'
import MaturityPage from './MaturityPage'

function OntologyRoutes() {
  return (
    <Routes>
      <Route index element={<OntologyPage />} />
      <Route path="maturity" element={<MaturityPage />} />
    </Routes>
  )
}

export default OntologyRoutes
