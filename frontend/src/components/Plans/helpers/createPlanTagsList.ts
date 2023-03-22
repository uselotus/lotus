import { components } from "../../../gen-types";

const createPlanTagsList = (
  planTags: any,
  orgPlanTypes: components["schemas"]["PlanDetail"]["tags"]
) => {
  const pt = [...planTags].map((el) => ({
    ...el,
    from: "plans",
  })) as components["schemas"]["PlanDetail"]["tags"];
  const flat = [...planTags].map((el) => el.tag_name);

  const opt = [...orgPlanTypes].map((el) => ({ ...el, from: "org" }));
  const t = [...pt, ...opt];
  // get non-distinct tag name values
  const nonDistinctTags = t.filter(
    (val) => val.from === "org" && !flat.includes(val.tag_name)
  );

  // get distinct tag name values
  const distinctTags = t.filter((val) =>
    pt.find((el) => el.tag_name === val.tag_name && val.from === "plans")
  );

  const tags = [...nonDistinctTags, ...distinctTags];

  return tags;
};
export default createPlanTagsList;
