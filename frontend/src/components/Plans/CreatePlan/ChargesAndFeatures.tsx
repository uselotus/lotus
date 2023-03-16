import React from "react";
import {
  Row,
  Card,
  Col,
  Form,
  Button,
  FormInstance,
  Typography,
  InputNumber,
  Select,
} from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { StepProps } from "./types";
import FeatureDisplay from "../FeatureDisplay";
import ComponentDisplay from "../ComponentDisplay";
import PlanRecurringCharges from "../PlanDetails/PlanRecurringCharges";
import capitalize from "../../../helpers/capitalize";
import removeUnderscore from "../../../helpers/removeUnderscore";
import createShortenedText from "../../../helpers/createShortenedText";
import CopyText from "../../base/CopytoClipboard";
import useMediaQuery from "../../../hooks/useWindowQuery";
import RecurringChargesDisplay from "../RecurringChargesDisplay";

export const validate = async (form: FormInstance<any>) => true;

const ChargesAndFeatures = ({ form, ...props }: StepProps) => {
  const windowWidth = useMediaQuery();

  React.useEffect(() => {
    props.setIsCurrentStepValid(true);
  }, [form, props]);

  return (
    <Row gutter={[24, 24]}>
      <Col span={24}>
        <Row gutter={[24, 24]}>
          {/* Recurring charges */}
          <Col span={24}>
            <Card
              title="Recurring Charges"
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
                <div>
                  <RecurringChargesDisplay
                    recurringCharges={props.recurringCharges}
                  />
                </div>

                <Button
                  key="add-recurring-charge"
                  htmlType="button"
                  type="primary"
                  className="hover:!bg-primary-700 mt-4"
                  style={{ background: "#C3986B", borderColor: "#C3986B" }}
                  onClick={() => props.setShowRecurringChargeModal(true)}
                >
                  <div className="flex items-center  justify-between text-white">
                    <div>
                      <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
                      Add Recurring Charges
                    </div>
                  </div>
                </Button>
              </Form.Item>
            </Card>
          </Col>

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
                  pricing_unit={props.selectedCurrency!}
                />

                <Button
                  key="add-component"
                  htmlType="button"
                  type="primary"
                  className="hover:!bg-primary-700 mt-4"
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
                  className="hover:!bg-primary-700 mt-4"
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

          <Col span="24">
            <Card
              className="w-12/12 mb-20"
              title="Discount"
              style={{
                borderRadius: "0.5rem",
                borderWidth: "2px",
                borderColor: "#EAEAEB",
                borderStyle: "solid",
              }}
            >
              <div className="grid grid-cols-2">
                <Form.Item
                  wrapperCol={{ span: 20 }}
                  label="Type"
                  name="price_adjustment_type"
                >
                  <Select
                    onChange={(value) => {
                      props.setPriceAdjustmentType(value);
                    }}
                  >
                    <Select.Option value="none">None</Select.Option>
                    {/* <Select.Option value="price_override">
                        Overwrite Price
                      </Select.Option> */}
                    <Select.Option value="percentage">
                      Percentage Off
                    </Select.Option>
                    <Select.Option value="fixed">Flat Discount</Select.Option>
                  </Select>
                </Form.Item>

                {props.priceAdjustmentType !== "none" && (
                  <Form.Item
                    name="price_adjustment_amount"
                    label="Amount"
                    wrapperCol={{ span: 24 }}
                    shouldUpdate={(prevValues, curValues) =>
                      prevValues.price_adjustment_type !==
                      curValues.price_adjustment_type
                    }
                    rules={[
                      {
                        required:
                          !!props.priceAdjustmentType ||
                          props.priceAdjustmentType !== "none",
                        message: "Please enter a price adjustment value",
                      },
                    ]}
                  >
                    <InputNumber
                      addonAfter={
                        props.priceAdjustmentType === "percentage" ? "%" : null
                      }
                      addonBefore={
                        (props.priceAdjustmentType === "fixed" ||
                          props.priceAdjustmentType === "price_override") &&
                        props.selectedCurrency
                          ? props.selectedCurrency.symbol
                          : null
                      }
                    />
                  </Form.Item>
                )}
              </div>
            </Card>
          </Col>
        </Row>
      </Col>
    </Row>
  );
};

export default ChargesAndFeatures;
