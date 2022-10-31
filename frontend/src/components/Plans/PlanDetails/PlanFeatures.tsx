// @ts-ignore
import React, { FC } from "react";
import "./PlanDetails.css";
import { FeatureType } from "../../../types/feature-type";

interface PlanFeaturesProps {
  features?: FeatureType[];
}

const PlanFeatures: FC<PlanFeaturesProps> = ({ features }) => {
  return (
    <>
      <div className="pb-5 pt-3 font-main font-bold text-[20px]">Features:</div>
      <div className="flex items-center justify-start flex-wrap">
        {features && features.length > 0 ? (
          features.map((feature) => (
            <div className=" py-2 bg-[#FAFAFA] rounded planComponent mr-4 mb-2">
              <div className="planDetails planComponentMetricName px-4">
                <div className="pr-1">{feature.feature_name}</div>
              </div>
              <div className="planFeatureDesc px-4">
                {feature.feature_description}
              </div>
            </div>
          ))
        ) : (
          <div className="flex items-center justify-start flex-wrap">
            No features
          </div>
        )}
      </div>
    </>
  );
};
export default PlanFeatures;
