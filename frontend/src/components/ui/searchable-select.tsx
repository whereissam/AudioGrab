import * as React from 'react'
import * as SelectPrimitive from '@radix-ui/react-select'
import { Check, ChevronDown, Search } from 'lucide-react'
import { cn } from '@/lib/utils'

// Radix doesn't allow empty string values, so we use a placeholder
const EMPTY_VALUE = '__EMPTY__'

interface SelectOption {
  value: string
  label: string
}

interface SearchableSelectProps {
  value: string
  onValueChange: (value: string) => void
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  className?: string
}

export function SearchableSelect({
  value,
  onValueChange,
  options,
  placeholder = 'Select...',
  disabled = false,
  className,
}: SearchableSelectProps) {
  const [search, setSearch] = React.useState('')
  const [open, setOpen] = React.useState(false)

  // Convert empty string to placeholder value for Radix
  const internalValue = value === '' ? EMPTY_VALUE : value

  // Convert options - replace empty string values with placeholder
  const internalOptions = React.useMemo(() => {
    return options.map(opt => ({
      ...opt,
      value: opt.value === '' ? EMPTY_VALUE : opt.value
    }))
  }, [options])

  const filteredOptions = React.useMemo(() => {
    if (!search) return internalOptions
    const lower = search.toLowerCase()
    return internalOptions.filter(
      (opt) =>
        opt.label.toLowerCase().includes(lower) ||
        (opt.value !== EMPTY_VALUE && opt.value.toLowerCase().includes(lower))
    )
  }, [internalOptions, search])

  const selectedLabel = React.useMemo(() => {
    const selected = internalOptions.find((opt) => opt.value === internalValue)
    return selected?.label || placeholder
  }, [internalOptions, internalValue, placeholder])

  const handleValueChange = (newValue: string) => {
    // Convert placeholder back to empty string
    onValueChange(newValue === EMPTY_VALUE ? '' : newValue)
  }

  // Reset search when closing
  React.useEffect(() => {
    if (!open) {
      setSearch('')
    }
  }, [open])

  return (
    <SelectPrimitive.Root
      value={internalValue}
      onValueChange={handleValueChange}
      open={open}
      onOpenChange={setOpen}
      disabled={disabled}
    >
      <SelectPrimitive.Trigger
        className={cn(
          'flex h-10 w-full items-center justify-between rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
      >
        <SelectPrimitive.Value placeholder={placeholder}>
          {selectedLabel}
        </SelectPrimitive.Value>
        <SelectPrimitive.Icon>
          <ChevronDown className="h-4 w-4 opacity-50" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>

      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          className="relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md animate-in fade-in-80"
          position="popper"
          sideOffset={4}
        >
          {/* Search Input */}
          <div className="flex items-center border-b px-3 py-2">
            <Search className="mr-2 h-4 w-4 shrink-0 opacity-50" />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex h-8 w-full rounded-md bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              onKeyDown={(e) => {
                // Prevent select from handling these keys
                e.stopPropagation()
              }}
            />
          </div>

          <SelectPrimitive.Viewport className="max-h-60 overflow-y-auto p-1">
            {filteredOptions.length === 0 ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                No results found
              </div>
            ) : (
              filteredOptions.map((option) => (
                <SelectPrimitive.Item
                  key={option.value}
                  value={option.value}
                  className="relative flex w-full cursor-default select-none items-center rounded-sm py-2 pl-8 pr-2 text-sm outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                >
                  <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                    <SelectPrimitive.ItemIndicator>
                      <Check className="h-4 w-4" />
                    </SelectPrimitive.ItemIndicator>
                  </span>
                  <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                </SelectPrimitive.Item>
              ))
            )}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}
