import React, { FC } from "react";
import { Button } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { FeatureType } from "../../types/feature-type";
import createShortenedText from "../../helpers/createShortenedText";
import CopyText from "../base/CopytoClipboard";
import useMediaQuery from "../../hooks/useWindowQuery";

export const FeatureDisplay: FC<{
  planFeatures: FeatureType[];
  editFeatures: (any) => void;
  removeFeature: (any) => void;
}> = ({ planFeatures, editFeatures, removeFeature }) => {
  const windowWidth = useMediaQuery();

  return (
    <div className="grid gap-6 grid-cols-1 xl:grid-cols-4">
      {planFeatures ? (
        planFeatures.map((feature) => (
          <div
            key={feature.feature_id}
            className="pt-2 pb-4 bg-primary-50 mt-2  mb-2 p-4 min-h-[152px]"
          >
            <div className="text-base text-card-text">
              <div className="flex justify-between items-center">
                {feature.feature_name}
                <Button
                  size="small"
                  type="text"
                  icon={<DeleteOutlined />}
                  danger
                  onClick={() => removeFeature(feature.feature_id)}
                />
              </div>
              <div className="flex gap-1 text-card-grey font-menlo">
                {" "}
                <div>
                  {createShortenedText(feature.feature_id, windowWidth >= 2500)}
                </div>
                <CopyText showIcon onlyIcon textToCopy={feature.feature_id} />
              </div>
            </div>
            <div />
            <div className="text-card-grey">{feature.feature_description}</div>
          </div>
        ))
      ) : (
        <div className="text-card-grey">No features added</div>
      )}
    </div>
  );
};

export default FeatureDisplay;
