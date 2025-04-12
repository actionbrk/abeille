export interface Choice {
  name: string;
  description: string;
  localizedNames?: Record<string, string>;
  localizedDescriptions?: Record<string, string>;
}

export interface TranslationOptions {
  name: string;
  description: string;
  localizedNames?: Record<string, string>;
  localizedDescriptions?: Record<string, string>;
  choices?: Record<string, Choice>;
}

export interface Translation {
  commands: {
    [key: string]: {
      name: string;
      description: string;
      options?: { [optionName: string]: TranslationOptions };
      responses?: Record<string, string>;
    };
  };
}
