import {
  forwardRef,
  type InputHTMLAttributes,
  type LabelHTMLAttributes,
  type TextareaHTMLAttributes,
  type SelectHTMLAttributes,
  type ReactNode,
} from "react"
import clsx from "clsx"

const fieldClasses =
  "block w-full rounded-lg border border-ink-200 bg-white px-3.5 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:bg-ink-50 disabled:text-ink-400"

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...rest }, ref) => <input ref={ref} className={clsx(fieldClasses, className)} {...rest} />
)
Input.displayName = "Input"

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...rest }, ref) => (
    <textarea ref={ref} className={clsx(fieldClasses, "min-h-28 resize-y", className)} {...rest} />
  )
)
Textarea.displayName = "Textarea"

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...rest }, ref) => (
    <select ref={ref} className={clsx(fieldClasses, "pr-8", className)} {...rest}>
      {children}
    </select>
  )
)
Select.displayName = "Select"

export function Label({ className, ...rest }: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label className={clsx("mb-1.5 block text-sm font-medium text-ink-700", className)} {...rest} />
}

export function FieldGroup({ children }: { children: ReactNode }) {
  return <div className="mb-4">{children}</div>
}
