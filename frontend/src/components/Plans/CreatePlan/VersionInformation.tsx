import React from "react";
import moment from "moment";
import {
  Row,
  Card,
  Col,
  Input,
  InputNumber,
  Select,
  Form,
  Radio,
  FormInstance,
} from "antd";
import { StepProps } from "./types";
import clsx from "clsx";

const fields = ["align_plan", "localized_name", "plan_currency"];

export const validate = async (form: FormInstance<any>) => {
  try {
    await form.validateFields(fields);
  } catch (err) {
    return false;
  }

  return true;
};

const VersionInformation = ({ form, ...props }: StepProps) => {
  const months = moment.months();

  React.useEffect(() => {
    const isValid = fields.every((field) => form.getFieldValue(field));

    props.setIsCurrentStepValid(isValid);
  }, [form, props]);

  return (
    <Row gutter={[24, 24]}>
      <Col span="24">
        <Row gutter={[24, 24]}>
          <Col span={24}>
            <Card title="Version Information" className="w-full">
              <Input.Group>
                <Row gutter={[24, 24]}>
                  <Col span="24">
                    <Form.Item
                      label="Invoice Time"
                      name="align_plan"
                      rules={[
                        {
                          required: true,
                          message: "Please Select One",
                        },
                      ]}
                    >
                      <Radio.Group>
                        <Radio value="calendar_aligned">
                          Every{" "}
                          <Form.Item name="day_of_month" noStyle>
                            <InputNumber
                              min={1}
                              max={31}
                              size="small"
                              style={{ width: "50px" }}
                              placeholder="Day"
                            />
                          </Form.Item>{" "}
                          {["quarterly", "yearly"].includes(
                            form.getFieldValue("plan_duration")
                          ) && (
                            <>
                              of{" "}
                              <Form.Item name="month_of_year" noStyle>
                                <select
                                  className="border border-black rounded-sm outline-none"
                                  onChange={(e) =>
                                    setMonth(Number(e.target.value))
                                  }
                                  name="month_of_year"
                                  id="month_of_year"
                                >
                                  {months.map((month, i) => (
                                    <option value={i + 1} key={month}>
                                      {month}
                                    </option>
                                  ))}
                                </select>
                              </Form.Item>
                            </>
                          )}
                          {["monthly"].includes(
                            form.getFieldValue("plan_duration")
                          ) && "of the Month"}
                        </Radio>
                        <Radio value="subscription_aligned">
                          Start of Subscription
                        </Radio>
                      </Radio.Group>
                    </Form.Item>
                  </Col>

                  <Col span="12">
                    <Form.Item
                      label="Localized Name"
                      name="localized_name"
                      rules={[
                        {
                          required: true,
                          message: "Please Enter a Name",
                        },
                      ]}
                      initialValue={form.getFieldValue("name")}
                    >
                      <Input
                        type="text"
                        id="planLocalizedNameInput"
                        placeholder="Ex: Starter plan"
                      />
                    </Form.Item>
                  </Col>

                  <Col span="12">
                    <Form.Item
                      name="plan_currency"
                      label="Plan Currency"
                      rules={[
                        {
                          required: true,
                          message: "Please Select One",
                        },
                      ]}
                    >
                      <Select
                        style={{
                          border: "2px solid #C3986B",
                          padding: "4px",
                        }}
                        onChange={(value) => {
                          const selectedCurrency = props.allCurrencies.find(
                            (currency) => currency.code === value
                          );
                          if (selectedCurrency) {
                            props.setSelectedCurrency(selectedCurrency);
                          }
                        }}
                        value={props.selectedCurrency?.symbol}
                      >
                        {props.allCurrencies.map((currency) => (
                          <Select.Option
                            key={currency.code}
                            value={currency.code}
                          >
                            {currency.name} {currency.symbol}
                          </Select.Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </Col>

                  <Col span="12">
                    <Form.Item
                      name="transition_to_plan_id"
                      label="Plan on next cycle"
                    >
                      <Select>
                        {props.allPlans.map((plan) => (
                          <Select.Option
                            key={plan.plan_id}
                            value={plan.plan_id}
                          >
                            {plan.plan_name}
                          </Select.Option>
                        ))}
                      </Select>
                    </Form.Item>
                  </Col>
                </Row>
              </Input.Group>
            </Card>
          </Col>
        </Row>
      </Col>
    </Row>
  );
};

export default VersionInformation;
