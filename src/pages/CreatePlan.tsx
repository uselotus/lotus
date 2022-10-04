import {
  Button,
  Checkbox,
  Form,
  Card,
  Input,
  Select,
  InputNumber,
  PageHeader,
  List,
} from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import UsageComponentForm from "../components/Plans/UsageComponentForm";
import { useMutation, useQuery, UseQueryResult } from "react-query";
import { MetricNameType } from "../types/metric-type";
import { toast } from "react-toastify";
import { Features, Metrics } from "../api/api";
import { CreatePlanType, CreateComponent } from "../types/plan-type";
import { Plan } from "../api/api";
import { FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import { DeleteOutlined } from "@ant-design/icons";
import React from "react";

interface ComponentDisplay {
  metric: string;
  cost_per_batch: number;
  metric_units_per_batch: number;
  free_metric_units: number;
  max_metric_units: number;
}

const CreatePlan = () => {
  const [visible, setVisible] = useState(false);
  const [featureVisible, setFeatureVisible] = useState(false);
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<string[]>([]);
  const [form] = Form.useForm();
  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>([]);

  const addFeatures = (newFeatures: FeatureType[]) => {
    setPlanFeatures([...planFeatures, ...newFeatures]);
    setFeatureVisible(false);
  };

  useEffect(() => {
    Metrics.getMetrics().then((res) => {
      const data: MetricNameType[] = res;
      if (data) {
        const metricList: string[] = [];
        for (let i = 0; i < data.length; i++) {
          if (typeof data[i].billable_metric_name !== undefined) {
            metricList.push(data[i].billable_metric_name);
          }
        }
        setMetrics(metricList);
      }
    });
  }, []);

  const {
    data: features,
    isLoading,
    isError,
  }: UseQueryResult<FeatureType[]> = useQuery<FeatureType[]>(
    ["feature_list"],
    () =>
      Features.getFeatures().then((res) => {
        return res;
      })
  );

  const mutation = useMutation(
    (post: CreatePlanType) => Plan.createPlan(post),
    {
      onSuccess: () => {
        toast.success("Successfully created Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
        form.resetFields();
        navigate("/plans");
      },
      onError: () => {
        toast.error("Failed to create Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const onFinishFailed = (errorInfo: any) => {};

  const hideUserModal = () => {
    setVisible(false);
  };

  const showUserModal = () => {
    setVisible(true);
  };

  const hideFeatureModal = () => {
    setFeatureVisible(false);
  };

  const showFeatureModal = () => {
    setFeatureVisible(true);
  };

  const goBackPage = () => {
    navigate(-1);
  };

  const submitPricingPlan = () => {
    form
      .validateFields()
      .then((values) => {
        const usagecomponentslist: CreateComponent[] = [];
        const components = form.getFieldValue("components");
        if (components) {
          for (let i = 0; i < components.length; i++) {
            const usagecomponent: CreateComponent = {
              billable_metric_name: components[i].metric,
              cost_per_batch: components[i].cost_per_batch,
              metric_units_per_batch: components[i].metric_units_per_batch,
              free_metric_units: components[i].free_amount,
              max_metric_units: components[i].max_metric_units,
            };
            usagecomponentslist.push(usagecomponent);
          }
        }

        const plan: CreatePlanType = {
          name: values.name,
          description: values.description,
          flat_rate: values.flat_rate,
          pay_in_advance: values.pay_in_advance,
          interval: values.billing_interval,
          components: usagecomponentslist,
          features: planFeatures,
        };
        mutation.mutate(plan);
      })
      .catch((info) => {
        console.log("Validate Failed:", info);
      });
  };

  return (
    <div className="flex flex-col">
      <PageHeader
        className="site-page-header"
        onBack={goBackPage}
        title="Create Plan"
      />
      <Form.Provider
        onFormFinish={(name, { values, forms }) => {
          if (name === "component_form") {
            const { create_plan } = forms;
            const components = create_plan.getFieldValue("components") || [];
            create_plan.setFieldsValue({ components: [...components, values] });
            setVisible(false);
          }
        }}
      >
        <Form
          form={form}
          name="create_plan"
          initialValues={{ flat_rate: 0, pay_in_advance: true }}
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
        >
          <div className="grid grid-cols-2 space-x-4">
            <div className="mx-2 my-2">
              <h2 className="mb-4">Plan Info</h2>

              <Form.Item
                label="Plan Name"
                name="name"
                rules={[
                  {
                    required: true,
                    message: "Please Name Your Plan",
                  },
                ]}
              >
                <Input placeholder="Ex: Starter Plan" />
              </Form.Item>
              <Form.Item label="Description" name="description">
                <Input
                  type="textarea"
                  placeholder="Ex: Cheapest plan for small scale businesses"
                />
              </Form.Item>
              <Form.Item
                label="Billing Interval"
                name="billing_interval"
                rules={[
                  {
                    required: true,
                    message: "Please select an interval",
                  },
                ]}
              >
                <Select>
                  <Select.Option value="week">Weekly</Select.Option>
                  <Select.Option value="month">Monthly</Select.Option>
                  <Select.Option value="year">Yearly</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item name="flat_rate" label="Recurring Cost">
                <InputNumber addonBefore="$" defaultValue={0} precision={2} />
              </Form.Item>
              <Form.Item name="pay_in_advance">
                <Checkbox defaultChecked={true}>Pay In Advance </Checkbox>
              </Form.Item>
              <div className="flex flex-row justify-center">
                <Form.Item>
                  <Button
                    htmlType="button"
                    style={{ margin: "0 8px" }}
                    onClick={showUserModal}
                  >
                    Add Component
                  </Button>
                </Form.Item>
                <Form.Item>
                  <Button
                    htmlType="button"
                    style={{ margin: "0 8px" }}
                    onClick={showFeatureModal}
                  >
                    Add Feature(s)
                  </Button>
                </Form.Item>
              </div>
            </div>
            <div className="grid grid-rows-2">
              <div className="flex flex-col space-y-4">
                <h2>Added Components</h2>
                <Form.Item
                  className=""
                  shouldUpdate={(prevValues, curValues) =>
                    prevValues.components !== curValues.components
                  }
                >
                  {({ getFieldValue }) => {
                    const components: ComponentDisplay[] =
                      getFieldValue("components") || [];
                    console.log(components);
                    return components.length ? (
                      <List grid={{ gutter: 10, column: 3 }}>
                        {components.map((component, index) => (
                          <List.Item key={index}>
                            <Card title={component.metric}>
                              <p>
                                <b>Cost:</b> ${component.cost_per_batch} per{" "}
                                {component.metric_units_per_batch}{" "}
                                {component.metric_units_per_batch === 1
                                  ? "unit"
                                  : "units"}{" "}
                              </p>
                              <br />
                              <p>
                                <b>Free Units:</b> {component.free_metric_units}
                              </p>
                              <p>
                                <b>Max Units:</b> {component.max_metric_units}
                              </p>
                            </Card>
                          </List.Item>
                        ))}
                      </List>
                    ) : null;
                  }}
                </Form.Item>
              </div>

              <div className="flex flex-col space-y-4 overflow-auto">
                <h2 className="mb-4">Added Features</h2>
                <Form.Item
                  className="w-1/2"
                  shouldUpdate={(prevValues, curValues) =>
                    prevValues.components !== curValues.components
                  }
                >
                  {planFeatures.map((feature, index) => (
                    <div
                      key={index}
                      className="flex flex-row items-center h-10 p-3 bg-grey3"
                    >
                      <h3 className="justify-self-center">
                        {feature.feature_name}
                      </h3>
                      <div className="">
                        {" "}
                        <DeleteOutlined />
                      </div>
                    </div>
                  ))}
                </Form.Item>
              </div>
            </div>
          </div>

          <Form.Item>
            <Button
              type="primary"
              className="bg-black justify-self-end"
              htmlType="submit"
            >
              Submit
            </Button>
          </Form.Item>
        </Form>
        <UsageComponentForm
          visible={visible}
          onCancel={hideUserModal}
          metrics={metrics}
        />
        <FeatureForm
          visible={featureVisible}
          onCancel={hideFeatureModal}
          features={features}
          onAddFeatures={addFeatures}
        />
      </Form.Provider>
    </div>
  );
};

export default CreatePlan;
