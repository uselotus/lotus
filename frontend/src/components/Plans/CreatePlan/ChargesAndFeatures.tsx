import React from "react";
import { Row, Card, Col, Form, Button, FormInstance } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { StepProps } from "./types";
import FeatureDisplay from "../FeatureDisplay";
import ComponentDisplay from "../ComponentDisplay";

export const validate = async (form: FormInstance<any>) => true;

/**
 * TODO Soham:
 *
 * 1. Add a new field called "Recurring charges" that is a select input
 */

const ChargesAndFeatures = ({ ...props }: StepProps) => (
  <Row gutter={[24, 24]}>
    <Col span={24}>
      <Row gutter={[24, 24]}>

      {/* Components */}
      <Col span={24}>
          <Card
            title="Added Components"
            className="w-full h-full"
            style={{
              borderRadius: "0.5rem",
              borderWidth: "2px",
              borderColor: "#EAEAEB",
              borderStyle: "solid",
            }}
          >
            <Form.Item
              wrapperCol={{ span: 24 }}
              shouldUpdate={(prevValues, curValues) =>
                prevValues.components !== curValues.components
              }
            >
              <ComponentDisplay
                componentsData={props.componentsData}
                handleComponentEdit={props.handleComponentEdit}
                deleteComponent={props.deleteComponent}
                pricing_unit={props.selectedCurrency}
              />

              <Button
                key="add-component"
                htmlType="button"
                type="primary"
                className="hover:!bg-primary-700"
                style={{ background: "#C3986B", borderColor: "#C3986B" }}
                onClick={() => props.showComponentModal()}
              >
                <div className="flex items-center  justify-between text-white">
                  <div>
                    <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
                    Add Component
                  </div>
                </div>
              </Button>
            </Form.Item>
          </Card>
        </Col>

        {/* Plan Features */}
        <Col span="24">
          <Card
            className="w-full my-6"
            title="Added Features"
            style={{
              borderRadius: "0.5rem",
              borderWidth: "2px",
              borderColor: "#EAEAEB",
              borderStyle: "solid",
            }}
          >
            <Form.Item
              wrapperCol={{ span: 24 }}
              shouldUpdate={(prevValues, curValues) =>
                prevValues.components !== curValues.components
              }
            >
              <FeatureDisplay
                planFeatures={props.planFeatures}
                removeFeature={props.removeFeature}
                editFeatures={props.editFeatures}
              />

              <Button
                key="add-feature"
                htmlType="button"
                type="primary"
                onClick={props.showFeatureModal}
                className="hover:!bg-primary-700"
                style={{ background: "#C3986B", borderColor: "#C3986B" }}
              >
                <div className="flex items-center  justify-between text-white">
                  <div>
                    <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
                    Add Feature
                  </div>
                </div>
              </Button>
            </Form.Item>
          </Card>
        </Col>
      </Row>
    </Col>
  </Row>
);

export default ChargesAndFeatures;
