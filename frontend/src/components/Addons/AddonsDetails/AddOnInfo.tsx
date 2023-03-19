import React from "react";
import { Typography } from "antd";
import capitalize from "../../../helpers/capitalize";
import { AddOnType } from "../../../types/addon-type";
import createShortenedText from "../../../helpers/createShortenedText";
import CopyText from "../../base/CopytoClipboard";
import useMediaQuery from "../../../hooks/useWindowQuery";
import { components } from "../../../gen-types";

interface AddOnInfoProps {
  addOnInfo: components["schemas"]["AddOnDetail"];
}
export const constructBillType = (str: string) => {
  if (str.includes("_")) {
    return str
      .split("_")
      .map((el) => capitalize(el))
      .join(" ");
  }
  return str;
};
function AddOnInfo({ addOnInfo }: AddOnInfoProps) {
  const windowWidth = useMediaQuery();

  return (
    <div className="min-h-[200px]  w-full p-8 cursor-pointer font-alliance rounded-sm bg-card ">
      <Typography.Title className="pt-4 whitespace-pre-wrap grid gap-4 !text-[18px] items-center grid-cols-1 md:grid-cols-2">
        <div>Add-On Information</div>
      </Typography.Title>
      <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
      <div className="grid  items-center grid-cols-1 md:grid-cols-[repeat(2,_minmax(0,_0.3fr))]">
        <div className="w-[256px]">
          <div className="flex items-center justify-between text-card-text !gap-20 mb-1">
            <div className="font-normal text-card-text font-alliance whitespace-nowrap leading-4">
              Add-On ID
            </div>
            <div className="flex gap-1 !text-card-grey font-menlo">
              {" "}
              <div>
                {createShortenedText(
                  addOnInfo.addon_id as string,
                  windowWidth >= 2500
                )}
              </div>
              <CopyText
                showIcon
                onlyIcon
                textToCopy={addOnInfo.addon_id as string}
              />
            </div>
          </div>
          {/* <div className="flex items-center  text-card-text justify-between mb-1">
            <div className="text-card-text font-normal font-alliance whitespace-nowrap leading-4">
              Price
            </div>
            <div className="flex gap-1 text-left">
              {" "}
              <div className="text-gold Inter">{`${addOnInfo.versions[0].currency?.symbol}${addOnInfo.flat_rate}`}</div>
            </div>
          </div> */}
        </div>

        <div className="w-[256px]">
          <div className="flex items-center text-card-text justify-between gap-2 mb-1">
            <div className=" font-alliance font-normal whitespace-nowrap leading-4">
              Type
            </div>
            <div className="flex gap-1 ">
              {" "}
              <div className="!text-card-grey Inter">
                {capitalize(
                  constructBillType(addOnInfo.versions[0].addon_type)
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between text-card-text gap-2 mb-1">
            <div className="font-alliance font-normal whitespace-nowrap leading-4">
              Billing Frequency
            </div>
            <div>
              <div className="!text-card-grey Inter">
                {constructBillType(
                  addOnInfo.versions[0].billing_frequency as string
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
export default AddOnInfo;
