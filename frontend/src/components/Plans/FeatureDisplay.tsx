import React, { FC } from "react";
import { Button } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { FeatureType } from "../../types/feature-type";

export const FeatureDisplay: FC<{
  planFeatures: FeatureType[];
  editFeatures: (any) => void;
  removeFeature: (any) => void;
}> = ({ planFeatures, editFeatures, removeFeature }) => (
    <div className="flex items-center justify-start flex-wrap">
      {planFeatures.map((feature) => (
        <div key={feature.feature_id} className=" py-2 bg-[#FAFAFA] rounded planComponent mr-4 mb-2 border-2 border-solid border-[#EAEAEB]">
          <div className="planDetails planComponentMetricName px-4 justify-between text-[#1d1d1fd9]">
            <div className="pr-1 font-main font-bold">
              {feature.feature_name}
            </div>
            <Button
              size="small"
              type="text"
              icon={<DeleteOutlined />}
              danger
              onClick={() => removeFeature(feature.feature_id)}
            />
          </div>
          <div className="planFeatureDesc px-4">
            {feature.feature_description}
          </div>
        </div>
      ))}
    </div>
  );

export default FeatureDisplay;
