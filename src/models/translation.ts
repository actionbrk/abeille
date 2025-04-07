export interface Translation {
  commands: {
    [key: string]: {
      name: string;
      description: string;
      options?: { [optionName: string]: { name: string; description: string } };
    };
  };
}
