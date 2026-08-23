import { Routes, Route } from 'react-router-dom'
import CollectionPage from './CollectionPage'
import TodoListPage from './TodoListPage'

// 数据采集模块路由
function CollectionRoutes() {
  return (
    <Routes>
      <Route index element={<CollectionPage />} />
      <Route path="todos" element={<TodoListPage />} />
    </Routes>
  )
}

export default CollectionRoutes
