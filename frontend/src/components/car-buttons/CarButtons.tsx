import { ButtonProfileEditor } from "@/components/button-profile-editor"

export const CarButtons = () => (
  <section className="flex flex-col gap-4 overflow-auto p-4">
    <div>
    <h1 className="text-lg font-semibold">Buttons</h1>
    <p className="mt-1 text-sm text-muted-foreground">
            Click a button to change its command.
          </p>
          </div>

          <div className="max-w-xl">

    <ButtonProfileEditor />
          </div>
  </section>
)
