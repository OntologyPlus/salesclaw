import { Routes, Route } from 'react-router-dom'
import KnowledgeOverviewPage from './KnowledgeOverviewPage'
import DocumentListPage from './DocumentListPage'
import FaqListPage from './FaqListPage'

function KnowledgeRoutes() {
  return (
    <Routes>
      <Route index element={<KnowledgeOverviewPage />} />
      <Route path="documents" element={<DocumentListPage />} />
      <Route path="faqs" element={<FaqListPage />} />
    </Routes>
  )
}

export default KnowledgeRoutes
