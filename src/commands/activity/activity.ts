import { ComponentType, InteractionContextType, SlashCommandBuilder, StringSelectMenuBuilder, TextChannel } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { getActivity } from "../../database/bee-database";
import { type ChartConfiguration } from "chart.js";
import { ChartJSNodeCanvas, type ChartCallback } from "chartjs-node-canvas";
import logger from "../../logger";
import { addDays, format } from "date-fns";
import { enUS } from "date-fns/locale";
import pl from "nodejs-polars";
import sharp from "sharp";

const translations = LocaleHelper.getCommandTranslations("activity");

const chartCallback: ChartCallback = (ChartJS) => {
  ChartJS.defaults.responsive = false;
  ChartJS.defaults.maintainAspectRatio = false;
};
const chartJSNodeCanvas = new ChartJSNodeCanvas({
  width: 700,
  height: 500,
  backgroundColour: "#111111",
  chartCallback,
  plugins: {
    globalVariableLegacy: ["chartjs-adapter-date-fns"],
  },
});

const ACTIVITY_PERIOD_ID = "activity-period";
const ACTIVITY_ROLLING_ID = "activity-rolling";

const ActivityCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("activity")
    .setNameLocalizations(translations.localizedNames)
    .setDescription(translations.localizedDescriptions["en-US"]!)
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .addChannelOption((option) =>
      option
        .setName("channel")
        .setNameLocalizations(translations.options!.channel!.localizedNames)
        .setDescription(translations.options!.channel!.localizedDescriptions["en-US"]!)
        .setDescriptionLocalizations(translations.options!.channel!.localizedDescriptions)
        .setRequired(false)
    ),
  async execute(interaction) {
    await interaction.deferReply();

    const guildId = interaction.guildId!;
    const channel = interaction.options.getChannel("channel");
    if (!!channel && !(channel instanceof TextChannel)) {
      return;
    }
    const userLocale: string = interaction.locale;
    const serverName = interaction.guild?.name ?? "Unknown Server";
    const botName = `${interaction.client.user?.username ?? ""}#${interaction.client.user?.discriminator ?? ""}`;

    const fileBuffer = await plotTrend(guildId, userLocale, serverName, botName, channel);

    const trendPeriodSelect = new StringSelectMenuBuilder().setCustomId(ACTIVITY_PERIOD_ID).setOptions([
      {
        label: translations.responses?.sinceTheBeginning?.[userLocale] ?? "Since the beginning",
        value: "0",
        description:
          translations.responses?.sinceTheBeginningDescription?.[userLocale] ??
          "Show the trend since the server's inception.",
        default: true,
      },
      {
        label: translations.responses?.forOneYear?.[userLocale] ?? "Trend for 1 year",
        value: "1",
        description: translations.responses?.forOneYearDescription?.[userLocale] ?? "Show the trend for 1 year.",
      },
      {
        label: translations.responses?.forTwoYears?.[userLocale] ?? "Trend for 2 years",
        value: "2",
        description: translations.responses?.forTwoYearsDescription?.[userLocale] ?? "Show the trend for 2 years.",
      },
      {
        label: translations.responses?.forThreeYears?.[userLocale] ?? "Trend for 3 years",
        value: "3",
        description: translations.responses?.forThreeYearsDescription?.[userLocale] ?? "Show the trend for 3 years.",
      },
    ]);

    const rollingMeanSelect = new StringSelectMenuBuilder().setCustomId(ACTIVITY_ROLLING_ID).setOptions([
      {
        label: translations.responses?.rolling14Days?.[userLocale] ?? "Average over 14 days",
        value: "14",
        description: translations.responses?.rolling14DaysDescription?.[userLocale] ?? "Rolling average over 14 days",
        default: true,
      },
      {
        label: translations.responses?.rolling7Days?.[userLocale] ?? "Average over 7 days",
        value: "7",
        description: translations.responses?.rolling7DaysDescription?.[userLocale] ?? "Rolling average over 7 days",
      },
      {
        label: translations.responses?.noRolling?.[userLocale] ?? "No rolling average",
        value: "1",
        description: translations.responses?.noRollingDescription?.[userLocale] ?? "Remove the rolling average",
      },
    ]);

    const components = [
      {
        type: ComponentType.ActionRow,
        components: [trendPeriodSelect],
      },
      {
        type: ComponentType.ActionRow,
        components: [rollingMeanSelect],
      },
    ];

    const message = await interaction.editReply({
      files: [
        {
          attachment: fileBuffer,
          name: "abeille.webp",
          contentType: "image/webp",
        },
      ],
      components: components,
    });

    const collector = message.createMessageComponentCollector({
      componentType: ComponentType.StringSelect,
      time: 10 * 60 * 1000,
    });

    let period = 0;
    let rolling = 14;

    collector.on("collect", async (i) => {
      if (i.customId === ACTIVITY_PERIOD_ID) {
        period = parseInt(i.values[0] ?? "0");
      } else if (i.customId === ACTIVITY_ROLLING_ID) {
        rolling = parseInt(i.values[0] ?? "14");
      }
      logger.debug("Period: %d, Rolling: %d", period, rolling);

      if (i.customId === ACTIVITY_PERIOD_ID) {
        const selectedPeriodOption = trendPeriodSelect.options.find((option) => option.data.value === i.values[0]);
        if (selectedPeriodOption) {
          trendPeriodSelect.options.forEach((option) => {
            option.setDefault(false);
          });
          selectedPeriodOption.setDefault(true);
        }
      } else if (i.customId === ACTIVITY_ROLLING_ID) {
        const selectedRollingOption = rollingMeanSelect.options.find((option) => option.data.value === i.values[0]);
        if (selectedRollingOption) {
          rollingMeanSelect.options.forEach((option) => {
            option.setDefault(false);
          });
          selectedRollingOption.setDefault(true);
        }
      }

      const deferUpdatePromise = i.update({ content: "", components: components });

      const newFileBuffer = await plotTrend(guildId, userLocale, serverName, botName, channel, rolling, period);
      await deferUpdatePromise;
      await i.editReply({
        files: [
          {
            attachment: newFileBuffer,
            name: "abeille.webp",
            contentType: "image/webp",
          },
        ],
      });
    });

    collector.on("end", async () => {
      logger.debug("Collector ended");
      await interaction.editReply({
        components: [],
      });
    });
  },
};

async function plotTrend(
  guildId: string,
  userLocale: string,
  serverName: string,
  botName: string,
  channel: TextChannel | null,
  rolling = 14,
  dateMode = 0
): Promise<Buffer<ArrayBufferLike>> {
  const activityResults = getActivity(guildId, channel?.id);
  logger.debug("Activity results: %o", activityResults);

  const endDate = activityResults.guildLastMessageDate ?? new Date();
  const startDate =
    dateMode === 0
      ? activityResults.guildFirstMessageDate ?? new Date()
      : endDate.getTime() - dateMode * 365 * 24 * 60 * 60 * 1000;
  const trends: { x: string; y: number }[] = [];

  let date = new Date(startDate);
  const trendMap = new Map(activityResults.activity.map((t) => [t.date, t.messages ?? 0]));
  while (date <= endDate) {
    const dateAsStr = format(date, "yyyy-MM-dd");
    const value = trendMap.get(dateAsStr) || 0;
    trends.push({ x: dateAsStr, y: value });
    date = addDays(date, 1);
  }

  let dataFrame = pl.DataFrame(trends);
  dataFrame = dataFrame
    .withColumn(pl.col("x").cast(pl.Date))
    .withColumn(pl.col("y").rollingMean({ windowSize: rolling }).fillNull(0));
  logger.debug("DataFrame: %o", dataFrame);

  // Dynamically load the locale based on the user's locale
  // Default to en-US if the locale is not found
  let locale = (await import("date-fns/locale/" + userLocale))[userLocale.replace("-", "")];
  if (!locale) {
    locale = enUS;
  }

  const dataFrameObject = dataFrame.toRecords();
  logger.debug("DataFrame object: %o", dataFrameObject);

  const chartConfiguration: ChartConfiguration<"line", { x: Date; y: number }[]> = {
    type: "line",
    data: {
      datasets: [
        {
          data: dataFrameObject as unknown as { x: Date; y: number }[],
          borderWidth: 3,
          borderColor: "rgb(255, 255, 0)",
          backgroundColor: "rgb(136, 136, 8)",
          fill: true,
          normalized: true,
        },
      ],
    },
    options: {
      animation: false,
      responsive: false,
      devicePixelRatio: 2,
      datasets: {
        line: {
          borderWidth: 1,
          pointStyle: false,
          cubicInterpolationMode: rolling === 0 ? "monotone" : "default",
          borderJoinStyle: "round",
        },
      },
      layout: {
        padding: {
          top: 10,
          bottom: 15,
          right: 25,
          left: 25,
        },
      },
      locale: userLocale,
      scales: {
        y: {
          type: "linear",
          alignToPixels: true,
          border: {
            display: false,
          },
          beginAtZero: true,
          min: 0,
          ticks: {
            callback: function (value) {
              const intValue = parseFloat(value.toString());
              return (100 * intValue).toFixed(2) + "%";
            },
            color: "white",
            autoSkip: true,
          },
          grid: {
            color: "rgb(88, 88, 88)",
          },
        },
        x: {
          type: "time",
          alignToPixels: true,
          border: {
            display: false,
          },
          ticks: {
            color: "white",
            autoSkip: true,
            maxRotation: 0,
            major: { enabled: true },
          },
          adapters: {
            date: {
              locale: locale,
            },
          },
          grid: {
            color: "rgb(88, 88, 88)",
          },
          title: {
            display: true,
            text: (translations.responses?.graphFooter?.[userLocale] ?? "Generated on {date} by {botName}")
              .replace("{date}", new Date().toLocaleString(userLocale, { dateStyle: "short" }))
              .replace("{botName}", botName),
            color: "white",
            align: "end",
            padding: { top: 10 },
            font: {
              size: 10,
            },
          },
        },
      },
      plugins: {
        colors: {
          enabled: true,
        },
        title: {
          text: (translations.responses?.graphTitle?.[userLocale] ?? "Message count per day"),
          font: {
            size: 18,
            weight: "bold",
          },
          display: true,
          align: "start",
          color: "white",
        },
        subtitle: {
          text: channel === null ?
            (translations.responses?.graphSubTitle?.[userLocale] ?? "On {serverName}")
              .replace("{serverName}", serverName)
            : (translations.responses?.graphSubTitleChannel?.[userLocale] ?? "On {serverName}, in channel: '{channelName}'")
              .replace("{serverName}", serverName)
              .replace("{channelName}", channel.name),
          display: true,
          align: "start",
          padding: { bottom: 25 },
          color: "white",
          font: {
            style: "italic",
          },
        },
        legend: {
          display: false,
        },
      },
    },
  };

  const buffer = await chartJSNodeCanvas.renderToBuffer(chartConfiguration as unknown as ChartConfiguration);
  return sharp(buffer).toFormat("webp", { quality: 80 }).toBuffer();
}

export default ActivityCommand;
