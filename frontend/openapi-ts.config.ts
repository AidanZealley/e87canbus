import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "../protocol/openapi.json",
  output: {
    path: "packages/coordinator-client/src/api/http",
    postProcess: ["prettier"],
  },
  plugins: [
    "@hey-api/typescript",
    {
      name: "@hey-api/client-fetch",
      runtimeConfigPath:
        "./packages/coordinator-client/src/api/http-client-config.ts",
      throwOnError: true,
    },
    "zod",
    {
      name: "@hey-api/sdk",
      responseStyle: "data",
      validator: {
        request: false,
        response: "zod",
      },
    },
    {
      name: "@tanstack/react-query",
      mutationOptions: true,
      queryKeys: true,
      queryOptions: true,
    },
  ],
})
