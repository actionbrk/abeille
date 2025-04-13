import type { ClientEvents } from "discord.js";

export interface BeeEvent<K extends keyof ClientEvents = never> {
  name: K;
  once: boolean;
  execute(...args: ClientEvents[K]): Promise<void>;
}
