import "../../node_modules/discord.js/typings/index";

import type { Collection } from "discord.js";
import type { Command } from "../models/command";

declare module "discord.js" {
  interface Client {
    commands?: Collection<string, Command>;
  }
}
