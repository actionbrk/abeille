export interface BeeEvent {
  name: string;
  execute(...args: unknown[]): Promise<void>;
  once?: boolean;
}
