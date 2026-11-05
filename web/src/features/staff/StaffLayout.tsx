import { NavLink, Outlet } from 'react-router'
import { STAFF_SECTIONS } from './sections.ts'
import styles from './StaffLayout.module.css'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? `${styles.link} ${styles.active}` : styles.link

/** Every /staff page: the portal's own menu beside the page. Inside RequireStaff. */
export function StaffLayout() {
  return (
    <div className={styles.layout}>
      <nav aria-label="Staff portal" className={styles.menu}>
        <NavLink to="/staff" end className={linkClass}>
          Overview
        </NavLink>
        {STAFF_SECTIONS.map((s) => (
          <NavLink key={s.path} to={`/staff/${s.path}`} className={linkClass}>
            {s.title}
          </NavLink>
        ))}
      </nav>
      <div className={styles.page}>
        <Outlet />
      </div>
    </div>
  )
}
