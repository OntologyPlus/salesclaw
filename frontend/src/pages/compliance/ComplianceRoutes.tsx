import { Routes, Route, Navigate } from 'react-router-dom'
import ComplianceOverviewPage from './ComplianceOverviewPage'
import ComplianceProfilePage from './ComplianceProfilePage'
import ComplianceCommitmentPage from './ComplianceCommitmentPage'
import ComplianceViolationPage from './ComplianceViolationPage'
import ComplianceForbiddenPage from './ComplianceForbiddenPage'
import ComplianceDisclosurePage from './ComplianceDisclosurePage'
import ComplianceSubmissionPage from './ComplianceSubmissionPage'
import ComplianceAuditPage from './ComplianceAuditPage'
import AuditPackPage from './AuditPackPage'

export default function ComplianceRoutes() {
  return (
    <Routes>
      <Route index element={<ComplianceOverviewPage />} />
      <Route path="profile" element={<ComplianceProfilePage />} />
      <Route path="commitment" element={<ComplianceCommitmentPage />} />
      <Route path="violation" element={<ComplianceViolationPage />} />
      <Route path="forbidden" element={<ComplianceForbiddenPage />} />
      <Route path="disclosure" element={<ComplianceDisclosurePage />} />
      <Route path="submission" element={<ComplianceSubmissionPage />} />
      <Route path="audit" element={<ComplianceAuditPage />} />
      <Route path="audit-pack" element={<AuditPackPage />} />
      <Route path="*" element={<Navigate to="/compliance" replace />} />
    </Routes>
  )
}
