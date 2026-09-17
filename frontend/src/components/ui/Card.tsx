import type { HTMLAttributes } from "react"
import clsx from "clsx"

export function Card({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={clsx("rounded-2xl border border-ink-100 bg-white shadow-sm", className)}
      {...rest}
    />
  )
}

export function CardHeader({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx("border-b border-ink-100 px-6 py-4", className)} {...rest} />
}

export function CardBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={clsx("px-6 py-5", className)} {...rest} />
}

export function CardTitle({ className, ...rest }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={clsx("text-base font-semibold text-ink-900", className)} {...rest} />
}
