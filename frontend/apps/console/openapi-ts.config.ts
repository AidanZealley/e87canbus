import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "../protocol/console-openapi.json",
  output: {
    path: "apps/console/src/api/console-host",
    postProcess: ["prettier"],
  },
  plugins: [
    "@hey-api/typescript",
    "@hey-api/client-fetch",
    "zod",
    {
      name: "@hey-api/sdk",
      responseStyle: "data",
      validator: {
        request: false,
        response: "zod",
      },
    },
  ],
})
