import clsx from "clsx"

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string }[]
  active: string
  onChange: (key: string) => void
}) {
  return (
    <div className="border-b border-ink-100">
      <nav className="-mb-px flex gap-6">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={clsx(
              "border-b-2 px-1 py-3 text-sm font-medium transition-colors",
              active === tab.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-ink-500 hover:border-ink-200 hover:text-ink-700"
            )}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  )
}
