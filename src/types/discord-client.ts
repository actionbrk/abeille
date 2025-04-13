import { Collection } from "discord.js";
import type { Command } from "../models/command";

declare module "discord.js" {
  export interface Client {
    commands?: Collection<string, Command>;
  }
}
