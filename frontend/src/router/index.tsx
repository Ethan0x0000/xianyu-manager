import { Navigate, Route, Routes } from 'react-router-dom'
import ProtectedRoute from '../components/ProtectedRoute'
import AppLayout from '../layouts/AppLayout'
import AboutPage from '../pages/AboutPage'
import AccountsPage from '../pages/AccountsPage'
import AutoReplyPage from '../pages/AutoReplyPage'
import CardsPage from '../pages/CardsPage'
import DashboardPage from '../pages/DashboardPage'
import DataManagementPage from '../pages/DataManagementPage'
import DeliveryPage from '../pages/DeliveryPage'
import ItemRepliesPage from '../pages/ItemRepliesPage'
import ItemSearchPage from '../pages/ItemSearchPage'
import ItemsPage from '../pages/ItemsPage'
import LoginPage from '../pages/LoginPage'
import LogsPage from '../pages/LogsPage'
import OnlineImPage from '../pages/OnlineImPage'
import OrdersPage from '../pages/OrdersPage'
import RiskLogsPage from '../pages/RiskLogsPage'
import SystemSettingsPage from '../pages/SystemSettingsPage'

export default function RouterOutlet() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate replace to="/dashboard" />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/items" element={<ItemsPage />} />
          <Route path="/item-replies" element={<ItemRepliesPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/auto-reply" element={<AutoReplyPage />} />
          <Route path="/cards" element={<CardsPage />} />
          <Route path="/delivery" element={<DeliveryPage />} />
          <Route path="/logs" element={<LogsPage />} />
          <Route path="/risk-logs" element={<RiskLogsPage />} />
          <Route path="/online-im" element={<OnlineImPage />} />
          <Route path="/item-search" element={<ItemSearchPage />} />
          <Route path="/system-settings" element={<SystemSettingsPage />} />
          <Route path="/data-management" element={<DataManagementPage />} />
          <Route path="/about" element={<AboutPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate replace to="/dashboard" />} />
    </Routes>
  )
}
