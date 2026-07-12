import * as SwitchPrimitive from "@radix-ui/react-switch"

export function Switch(props: SwitchPrimitive.SwitchProps) {
  return (
    <SwitchPrimitive.Root
      className="relative h-5 w-9 rounded-full bg-input transition-colors data-[state=checked]:bg-primary"
      {...props}
    >
      <SwitchPrimitive.Thumb className="block h-4 w-4 translate-x-0.5 rounded-full bg-background transition-transform data-[state=checked]:translate-x-4" />
    </SwitchPrimitive.Root>
  )
}
