import { createRouter } from "@tanstack/react-router"

import { routeTree } from "@/routeTree.gen"

export const router = createRouter({
  routeTree,
  defaultPreload: "intent",
  scrollRestoration: true,
  notFoundMode: "root",
})

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}
