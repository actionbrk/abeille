import { InteractionContextType, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { getTrend } from "../../database/bee-database";
import { type ChartConfiguration } from "chart.js";
import { ChartJSNodeCanvas, type ChartCallback } from "chartjs-node-canvas";
import logger from "../../logger";
import { addDays, format } from "date-fns";
import { enUS } from "date-fns/locale";

const translations = LocaleHelper.getCommandTranslations("trend");

const chartCallback: ChartCallback = (ChartJS) => {
  ChartJS.defaults.responsive = false;
  ChartJS.defaults.maintainAspectRatio = false;
};
const chartJSNodeCanvas = new ChartJSNodeCanvas({
  width: 600,
  height: 400,
  backgroundColour: "#111111",
  chartCallback,
  plugins: {
    globalVariableLegacy: ["chartjs-adapter-date-fns"],
  },
});

const TrendCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("trend")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Draw the trend of an expression.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .addStringOption((option) =>
      option
        .setName("term")
        .setNameLocalizations(translations.options!.term!.localizedNames)
        .setDescription("The term to draw the trend for.")
        .setDescriptionLocalizations(translations.options!.term!.localizedDescriptions)
        .setRequired(true)
        .setMinLength(3)
        .setMaxLength(50)
    ),
  async execute(interaction) {
    if (!interaction.inGuild()) {
      await interaction.reply({
        content: "This command can only be used in a server.",
        flags: [MessageFlags.Ephemeral],
      });
      return;
    }

    await interaction.deferReply();
    const guildId = interaction.guildId;
    const term = interaction.options.getString("term", true);
    const userLocale = interaction.locale;
    const fileBuffer = await plotTrend(guildId, term, userLocale);

    await interaction.editReply({
      files: [
        {
          attachment: fileBuffer,
          name: "trend.png",
        },
      ],
    });
  },
};

async function plotTrend(
  guildId: string,
  term: string,
  userLocale: string,
  rolling = 14
): Promise<Buffer<ArrayBufferLike>> {
  const trendResults = getTrend(guildId, term);
  logger.debug("Trend results: %o", trendResults);

  const startDate = trendResults.guildFirstMessageDate ?? new Date();
  const endDate = trendResults.guildLastMessageDate ?? new Date();
  const trends: { x: string; y: number }[] = [];

  let maxValue = 0;

  let date = new Date(startDate);
  while (date <= endDate) {
    const dateAsStr = format(date, "yyyy-MM-dd");
    const trendResult = trendResults.trend.find((t) => dateAsStr == t.date);
    const value = trendResult?.messages ?? 0;
    if (value > maxValue) {
      maxValue = value;
    }
    trends.push({ x: format(date, "yyyy-MM-dd"), y: value });
    date = addDays(date, 1);
  }

  // Dynamically load the locale based on the user's locale
  // Default to en-US if the locale is not found
  let locale = (await import("date-fns/locale/" + userLocale))[userLocale.replace("-", "")];
  if (!locale) {
    locale = enUS;
  }

  const chartConfiguration: ChartConfiguration<"line", { x: string; y: number }[]> = {
    type: "line",
    data: {
      datasets: [
        {
          data: trends,
          borderColor: "rgb(255, 255, 0)",
        },
      ],
    },
    options: {
      animation: false,
      responsive: false,
      devicePixelRatio: 4,
      datasets: {
        line: {
          borderWidth: 1,
          pointStyle: false,
          cubicInterpolationMode: "monotone",
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: function (value) {
              const intValue = parseFloat(value.toString());
              return 100 * intValue + "%";
            },
          },
        },
        x: {
          type: "time",
          adapters: {
            date: {
              locale: locale,
            },
          },
        },
      },
      plugins: {
        colors: {
          enabled: true,
        },
        title: {
          text: "Trends",
          display: true,
          align: "start",
          fullSize: false,
        },
        subtitle: {
          text: "Rolling average",
          display: true,
          align: "start",
          padding: { bottom: 15 },
          fullSize: false,
        },
        legend: {
          display: false,
        },
      },
    },
  };

  const buffer = await chartJSNodeCanvas.renderToBuffer(chartConfiguration as unknown as ChartConfiguration);
  return buffer;
}

export default TrendCommand;
