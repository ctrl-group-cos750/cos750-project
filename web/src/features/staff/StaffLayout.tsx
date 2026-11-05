import { LayoutDashboard } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { cn } from '@/lib/utils'
import { STAFF_SECTIONS } from './sections.ts'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    buttonVariants({ variant: isActive ? 'secondary' : 'ghost', size: 'lg' }),
    'justify-start text-foreground',
  )

/** Every /staff page: the portal's own menu beside the page (above it on phones). Inside
 * RequireStaff. */
export function StaffLayout() {
  return (
    <div className="grid items-start gap-6 md:grid-cols-[12rem_minmax(0,1fr)]">
      <nav
        aria-label="Staff portal"
        className="flex flex-wrap gap-1 border-b border-border pb-3 md:sticky md:top-4 md:grid md:border-b-0 md:pb-0"
      >
        <NavLink to="/staff" end className={linkClass}>
          <LayoutDashboard aria-hidden />
          Overview
        </NavLink>
        {STAFF_SECTIONS.map(({ path, title, icon: Icon }) => (
          <NavLink key={path} to={`/staff/${path}`} className={linkClass}>
            <Icon aria-hidden />
            {title}
          </NavLink>
        ))}
      </nav>
      <div className="min-w-0">
        <Outlet />
      </div>
    </div>
  )
}
