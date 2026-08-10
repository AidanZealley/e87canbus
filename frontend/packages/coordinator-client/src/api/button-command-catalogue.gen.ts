// This file is auto-generated from protocol/openapi.json.
// Run `pnpm http:generate` after changing the backend button catalogue.

export type ButtonCommandFieldSpec =
  | {
      readonly name: string;
      readonly label: string;
      readonly kind: "enum";
      readonly values: readonly (string | number)[];
    }
  | {
      readonly name: string;
      readonly label: string;
      readonly kind: "boolean";
    }
  | {
      readonly name: string;
      readonly label: string;
      readonly kind: "integer";
      readonly minimum?: number;
      readonly maximum?: number;
    };

export type ButtonCommandSpec = {
  readonly type: string;
  readonly hasActiveState: boolean;
  readonly fields: readonly ButtonCommandFieldSpec[];
};

export const BUTTON_COMMAND_CATALOGUE = [
  {
    type: "select_steering_mode",
    hasActiveState: true,
    fields: [
      {
        name: "mode",
        label: "Mode",
        kind: "enum",
        values: ["auto", "manual"],
      },
    ],
  },
  {
    type: "toggle_automatic_assistance",
    hasActiveState: true,
    fields: [],
  },
  {
    type: "adjust_manual_assistance",
    hasActiveState: false,
    fields: [
      {
        name: "delta",
        label: "Delta",
        kind: "enum",
        values: [-1, 1],
      },
    ],
  },
  {
    type: "set_manual_assistance_level",
    hasActiveState: true,
    fields: [
      {
        name: "level",
        label: "Level",
        kind: "integer",
        minimum: 0,
      },
    ],
  },
  {
    type: "set_maximum_assistance",
    hasActiveState: true,
    fields: [
      {
        name: "enabled",
        label: "Enabled",
        kind: "boolean",
      },
    ],
  },
  {
    type: "toggle_maximum_assistance",
    hasActiveState: true,
    fields: [],
  },
  {
    type: "start_high_beam_strobe",
    hasActiveState: false,
    fields: [],
  },
] as const satisfies readonly ButtonCommandSpec[];
