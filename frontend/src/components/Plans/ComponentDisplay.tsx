import React, { FC } from "react";
import { Button, Row, Col, Descriptions } from "antd";
import { Paper } from "../base/Paper";
import { EditOutlined, DeleteOutlined } from "@ant-design/icons";

//standard react component FC with props {componentsData}
export const ComponentDisplay: FC<{
  componentsData: any;
  handleComponentEdit: (any) => void;
  deleteComponent: (any) => void;
}> = ({ componentsData, handleComponentEdit, deleteComponent }) => {
  return (
    <Row gutter={[12, 12]}>
      {componentsData?.map((component: any, index: number) => (
        <Col span="24" key={index}>
          <Paper>
            <Descriptions
              title={component?.metric}
              size="small"
              column={2}
              extra={[
                <Button
                  key="edit"
                  type="text"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => handleComponentEdit(component.id)}
                />,
                <Button
                  key="delete"
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  danger
                  onClick={() => deleteComponent(component.metric)}
                />,
              ]}
            >
              <Descriptions.Item label="Cost" span={4}>
                {component.cost_per_batch
                  ? `$${component.cost_per_batch} / ${component.metric_units_per_batch} Unit(s)`
                  : "Free"}
              </Descriptions.Item>
              <Descriptions.Item label="Free Units" span={1}>
                {component.free_metric_units ?? "Unlimited"}
              </Descriptions.Item>
              <Descriptions.Item label="Max Units" span={1}>
                {component.max_metric_units ?? "Unlimited"}
              </Descriptions.Item>
            </Descriptions>
          </Paper>
        </Col>
      ))}
    </Row>
  );
};

export default ComponentDisplay;
