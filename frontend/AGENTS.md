## Component Directory Structure

Components should follow this structure for organization and maintainability:

### Directory and File Naming

- **Directory name**: kebab-case (e.g., `example-card`, `shopping-list`)
- **Component file**: PascalCase matching the component name (e.g., `ExampleCard.tsx`, `ShoppingList.tsx`)
- **Index file**: `index.ts` that re-exports from the component file
- **Related files**: `types.ts` and `utils.ts` for component-specific types and utilities

### Example Structure

```
src/components/example-card/
├── ExampleCard.tsx    # Main component file
├── index.ts           # Re-exports: export * from "./ExampleCard"
├── types.ts           # Component-specific types
└── utils.ts           # Component-specific utilities
```

### Nested Components

For complex components, child/related components can be nested in a `components/` directory:

```
src/components/shopping-list/
├── ShoppingList.tsx
├── index.ts
├── types.ts
├── utils.ts
└── components/
    ├── editable-item-name/
    │   ├── EditableItemName.tsx
    │   ├── index.ts
    │   ├── types.ts
    │   └── utils.ts
    └── quantity-badge/
        ├── QuantityBadge.tsx
        ├── index.ts
        ├── types.ts
        └── utils.ts
```

### Component Export Syntax

Use named exports with `export const`:

```typescript
export const ExampleCard = () => {
  // component implementation
};
```

### One Component Per File

Prefer creating separate component files rather than defining multiple components in the same file. This improves:

- Code organization and maintainability
- Component reusability
- Import clarity

### Importing Components

Components can be imported using the directory path:

```typescript
import { ExampleCard } from "@/components/example-card";
import { EditableItemName } from "@/components/shopping-list/components/editable-item-name";
```
