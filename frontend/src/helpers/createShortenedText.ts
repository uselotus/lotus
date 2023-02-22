function createShortenedText(plan: string, isXL: boolean) {
  const { length } = plan.split("");
  const front = plan.split("").splice(0, 4);
  if (isXL && length < 17) {
    return plan;
  }
  if (!isXL && length < 14) {
    return plan;
  }
  const back = isXL
    ? plan.split("").slice(length - 11)
    : plan.split("").slice(length - 8);
  return `${front.join("")}...${back.join("")}`;
}
export default createShortenedText;
