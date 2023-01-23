// @ts-ignore
import React, { FC } from "react";
import "./PlanDetails.css";
import { FeatureType } from "../../../types/feature-type";
import { Typography } from "antd";
import CopyText from "../../base/CopytoClipboard";
import createShortenedText from "../../../helpers/createShortenedText";
import useMediaQuery from "../../../hooks/useWindowQuery";

interface PlanFeaturesProps {
  features?: FeatureType[];
}

const PlanFeatures: FC<PlanFeaturesProps> = ({ features }) => {
  const windowWidth = useMediaQuery();
  return (
    <div className="min-h-[200px] mt-4 min-w-[246px] p-8 cursor-pointer font-main rounded-sm bg-card ">
      <Typography.Title className="!text-[18px]" level={2}>
        Features
      </Typography.Title>
      <div className=" w-full h-[1.5px] mt-6 bg-card-divider mb-2" />
      <div className="grid gap-6 grid-cols-1 xl:grid-cols-4">
        {features && features.length > 0 ? (
          features.map((feature) => (
            <div className="pt-2 pb-4 bg-primary-50 mt-2  mb-2 p-4 min-h-[152px]">
              <div className="text-base text-card-text">
                <div>{feature.feature_name}</div>
                <div className="flex gap-1 text-card-grey font-menlo">
                  {" "}
                  <div>
                    {createShortenedText(
                      feature.feature_id,
                      windowWidth >= 2500
                    )}
                  </div>
                  <CopyText showIcon onlyIcon textToCopy={feature.feature_id} />
                </div>
              </div>
              <div></div>
              <div className="text-card-grey">
                {feature.feature_description}
              </div>
            </div>
          ))
        ) : (
          <div className="text-card-grey">No features added</div>
        )}
      </div>
    </div>
  );
};
export default PlanFeatures;
