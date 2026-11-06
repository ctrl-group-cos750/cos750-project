import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { CircleAlert, CircleCheck, Info, TriangleAlert } from 'lucide-react'
import { cn } from 'cn'

const alertVariants = cva(
  "group/alert relative grid w-full gap-0.5 rounded-lg border px-3 py-2.5 text-left text-sm has-data-[slot=alert-action]:relative has-data-[slot=alert-action]:pr-18 has-[>svg]:grid-cols-[auto_1fr] has-[>svg]:gap-x-2 *:[svg]:row-span-2 *:[svg]:translate-y-0.5 *:[svg]:text-current *:[svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: 'border-border bg-card text-card-foreground',
        info: 'border-primary/30 bg-accent text-accent-foreground *:data-[slot=alert-description]:text-accent-foreground',
        success:
          'border-success/30 bg-success-soft text-success *:data-[slot=alert-description]:text-foreground',
        warning:
          'border-warning/30 bg-warning-soft text-warning *:data-[slot=alert-description]:text-foreground',
        destructive:
          'border-destructive/30 bg-destructive-soft text-destructive *:data-[slot=alert-description]:text-foreground',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
)

type AlertVariant = NonNullable<VariantProps<typeof alertVariants>['variant']>

const icons: Record<AlertVariant, React.ComponentType<{ 'aria-hidden'?: boolean }> | null> = {
  default: null,
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  destructive: CircleAlert,
}

/**
 * Feedback after an action. Each tone has its own icon, so the meaning never relies on colour
 * alone. Destructive alerts interrupt screen readers (role="alert"); the rest wait their turn
 * (role="status"). Pass `icon={false}` to leave the icon out.
 */
function Alert({
  className,
  variant = 'default',
  icon = true,
  role,
  children,
  ...props
}: React.ComponentProps<'div'> & VariantProps<typeof alertVariants> & { icon?: boolean }) {
  const Icon = icon ? icons[variant ?? 'default'] : null
  return (
    <div
      data-slot="alert"
      role={role ?? (variant === 'destructive' ? 'alert' : 'status')}
      className={cn(alertVariants({ variant }), className)}
      {...props}
    >
      {Icon && <Icon aria-hidden />}
      {children}
    </div>
  )
}

function AlertTitle({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        'font-semibold group-has-[>svg]/alert:col-start-2 [&_a]:underline [&_a]:underline-offset-3',
        className,
      )}
      {...props}
    />
  )
}

function AlertDescription({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        'text-sm text-pretty text-muted-foreground group-has-[>svg]/alert:col-start-2 [&_a]:underline [&_a]:underline-offset-3 [&_p:last-child]:mb-0 [&_p:not(:last-child)]:mb-2',
        className,
      )}
      {...props}
    />
  )
}

function AlertAction({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div data-slot="alert-action" className={cn('absolute top-2 right-2', className)} {...props} />
  )
}

export { Alert, AlertTitle, AlertDescription, AlertAction, type AlertVariant }
