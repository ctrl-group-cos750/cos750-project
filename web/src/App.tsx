import { Route, Routes } from 'react-router'
import { GuestOnly, RequireAuth, RequireStaff } from './auth/guards.tsx'
import { LoginPage } from './auth/LoginPage.tsx'
import { RegisterPage } from './auth/RegisterPage.tsx'
import { ReportPage } from './features/mastery/ReportPage.tsx'
import { ReviewPage } from './features/mastery/ReviewPage.tsx'
import { ProfilePage } from './features/profile/ProfilePage.tsx'
import { BadgesPage } from './features/rewards/BadgesPage.tsx'
import { StaffAccountPage } from './features/staff/StaffAccountPage.tsx'
import { StaffAccountsPage } from './features/staff/StaffAccountsPage.tsx'
import { StaffLayout } from './features/staff/StaffLayout.tsx'
import { StaffMembersPage } from './features/staff/StaffMembersPage.tsx'
import { StaffPilotPage } from './features/staff/StaffPilotPage.tsx'
import { StaffPortalPage } from './features/staff/StaffPortalPage.tsx'
import { StaffVideoImportPage } from './features/staff/StaffVideoImportPage.tsx'
import { StaffVideoEditorPage } from './features/staff/StaffVideoEditorPage.tsx'
import { StaffVideosPage } from './features/staff/StaffVideosPage.tsx'
import { VideoPage } from './features/video/VideoPage.tsx'
import { HomePage } from './pages/HomePage.tsx'
import { NotFoundPage } from './pages/NotFoundPage.tsx'
import { SignedInLayout } from './pages/SignedInLayout.tsx'

/** Every route in the app. Signed-in pages go inside the RequireAuth route. */
function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <GuestOnly>
            <LoginPage />
          </GuestOnly>
        }
      />
      <Route
        path="/register"
        element={
          <GuestOnly>
            <RegisterPage />
          </GuestOnly>
        }
      />
      <Route
        element={
          <RequireAuth>
            <SignedInLayout />
          </RequireAuth>
        }
      >
        <Route index element={<HomePage />} />
        <Route path="videos/:videoId" element={<VideoPage />} />
        <Route path="report" element={<ReportPage />} />
        <Route path="review/:objectiveId" element={<ReviewPage />} />
        <Route path="badges" element={<BadgesPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route
          path="staff"
          element={
            <RequireStaff>
              <StaffLayout />
            </RequireStaff>
          }
        >
          <Route index element={<StaffPortalPage />} />
          <Route path="videos" element={<StaffVideosPage />} />
          <Route path="videos/import" element={<StaffVideoImportPage />} />
          <Route path="videos/:videoId" element={<StaffVideoEditorPage />} />
          <Route path="accounts" element={<StaffAccountsPage />} />
          <Route path="accounts/:accountId" element={<StaffAccountPage />} />
          <Route path="pilot" element={<StaffPilotPage />} />
          <Route path="members" element={<StaffMembersPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default App
