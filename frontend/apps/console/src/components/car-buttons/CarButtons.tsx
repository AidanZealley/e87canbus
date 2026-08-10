import { ButtonProfileEditor } from "@/components/button-profile-editor"

export const CarButtons = () => (
  <section className="flex flex-col gap-4 overflow-auto p-4">
    <div>
      <h1 className="text-lg font-semibold">Buttons</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Configure each button&apos;s command and LED presentation.
      </p>
    </div>

    <div className="w-full max-w-3xl">
      <ButtonProfileEditor />
    </div>
  </section>
)
