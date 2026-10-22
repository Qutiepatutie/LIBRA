export default function getNiceScale(maxValue, maxTicks = 5) {
    const roughStep = maxValue / maxTicks;

    const magnitude = Math.pow(
        10,
        Math.floor(Math.log10(roughStep || 1))
    );

    const normalized = roughStep / magnitude;

    const steps = [1, 2, 5, 10];

    const niceStep =
        steps.find(step => step >= normalized) * magnitude;

    const interval = niceStep;
    const yAxisMax = Math.ceil(maxValue / interval) * interval;

    return { interval, yAxisMax };
};