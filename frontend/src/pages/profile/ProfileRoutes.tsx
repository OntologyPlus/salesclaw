import { Routes, Route } from 'react-router-dom'
import ProfilePage from './ProfilePage'

// 我的画像模块路由
function ProfileRoutes() {
  return (
    <Routes>
      <Route index element={<ProfilePage />} />
    </Routes>
  )
}

export default ProfileRoutes
