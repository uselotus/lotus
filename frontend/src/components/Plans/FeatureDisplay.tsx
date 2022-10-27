import React, { FC } from "react";
import { Button, Row, Col, Descriptions } from "antd";
import { Paper } from "../base/Paper";
import { EditOutlined, DeleteOutlined } from "@ant-design/icons";

//standard react component FC with props {componentsData}
export const FeatureDisplay: FC<{
  planFeatures: any;
  editFeatures: (any) => void;
  removeFeature: (any) => void;
}> = ({ planFeatures, editFeatures, removeFeature }) => {
  return (
    <Row gutter={[12, 12]}>
      {planFeatures.map((feature, index) => (
        <Col key={index} span={24}>
          <Paper>
            <div className="self-center">
              {" "}
              <Descriptions
                title={feature.feature_name}
                size="small"
                extra={[
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => editFeatures(feature.feature_name)}
                  />,
                  <Button
                    size="small"
                    type="text"
                    icon={<DeleteOutlined />}
                    danger
                    onClick={() => removeFeature(feature.feature_name)}
                  />,
                ]}
              />
            </div>
          </Paper>
        </Col>
      ))}
    </Row>
  );
};

export default FeatureDisplay;
