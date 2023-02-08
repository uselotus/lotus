const createDescription = (arr: string[]): string => {
  arr.splice(arr.length - 2, 2).join("");
  return arr.join(" ");
};
export default createDescription;
