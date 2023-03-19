/* eslint-disable camelcase */
import React, { FC, useRef } from "react";
import { Typography } from "antd";
import { useQueryClient } from "react-query";
import { useNavigate } from "react-router-dom";
import CopyText from "../../base/CopytoClipboard";
import createShortenedText from "../../../helpers/createShortenedText";
import capitalize from "../../../helpers/capitalize";
import useMediaQuery from "../../../hooks/useWindowQuery";
import { AddOnType } from "../../../types/addon-type";
import { constructBillType } from "../AddonsDetails/AddOnInfo";
import { components } from "../../../gen-types";

interface AddOnCardProps {
  add_on: components["schemas"]["AddOnDetail"];
}

const AddOnsCard: FC<AddOnCardProps> = ({ add_on }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const windowWidth = useMediaQuery();
  const inputRef = useRef<HTMLInputElement | null>(null!);

  const goToAddOnDetail = () => {
    navigate(`/add-ons/${add_on.addon_id}`);
  };

  return (
    <div
      className="min-h-[200px]  min-w-[246px] p-6 cursor-pointer  rounded-sm bg-card  shadow-lg hover:shadow-neutral-400"
      onClick={goToAddOnDetail}
      aria-hidden
    >
      <Typography.Title className="pt-4 flex font-alliance" level={2}>
        <span>{add_on.addon_name}</span>
      </Typography.Title>

      <div>
        <div>
          <div className="mb-2">
            <div className="pr-1 font-normal font-alliance not-italic whitespace-nowrap  text-darkgold">
              Total Active Customer: {add_on.versions[0].active_instances}
            </div>
            <div className=" w-full h-[1.5px] mt-6 bg-card-divider" />
          </div>

          <div className="flex items-center text-card-text justify-between gap-2 mb-1">
            <div className=" font-normal whitespace-nowrap leading-4">
              Add-On ID
            </div>
            <div className="flex gap-1 text-card-grey font-menlo">
              {" "}
              <div>
                {createShortenedText(add_on.addon_id, windowWidth >= 2500)}
              </div>
              <CopyText showIcon onlyIcon textToCopy={add_on.addon_id} />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">Type</div>
          <div className="text-card-grey font-main">
            {add_on.versions[0].addon_type}
          </div>
        </div>

        <div className="flex items-center text-card-text justify-between gap-2 mb-1">
          <div className="font-normal text-card-text whitespace-nowrap leading-4xs">
            Billing Frequency
          </div>
          <div className="text-card-grey font-main">
            {" "}
            {constructBillType(
              capitalize(add_on.versions[0].billing_frequency)
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
export default AddOnsCard;
