import {
  Button,
  Checkbox,
  Form,
  Card,
  Input,
  InputNumber,
  Row,
  Col,
  Radio,
  Descriptions,
} from "antd";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import UsageComponentForm from "../components/Plans/UsageComponentForm";
import { useMutation, useQueryClient } from "react-query";
import { toast } from "react-toastify";

import {
  CreatePlanType,
  CreateComponent,
  PlanType,
  UpdatePlanType,
} from "../types/plan-type";
import { Plan } from "../api/api";
import { FeatureType } from "../types/feature-type";
import FeatureForm from "../components/Plans/FeatureForm";
import {
  DeleteOutlined,
  ArrowLeftOutlined,
  SaveOutlined,
  EditOutlined,
} from "@ant-design/icons";
import React from "react";
import { Paper } from "../components/base/Paper";
import { PageLayout } from "../components/base/PageLayout";
import { usePlanState, usePlanUpdater } from "../context/PlanContext";

interface CustomizedState {
  plan: PlanType;
}

interface Props {
  type: "backtest" | "edit";
}

const EditPlan = ({ type }: Props) => {
  const [componentVisible, setcomponentVisible] = useState<boolean>();
  const [featureVisible, setFeatureVisible] = useState<boolean>(false);
  const location = useLocation();
  const { replacementPlan } = usePlanState();
  const { setReplacementPlan } = usePlanUpdater();
  const navigate = useNavigate();
  const [componentsData, setComponentsData] = useState<any>([]);
  const [form] = Form.useForm();
  const [editComponentItem, setEditComponentsItem] = useState<any>();
  const plan = React.useMemo(() => {
    if (type === "backtest") {
      return replacementPlan ?? {};
    }
    const { plan } = location.state.data as CustomizedState;
    return plan ?? {};
  }, [type]);

  const queryClient = useQueryClient();

  const [planFeatures, setPlanFeatures] = useState<FeatureType[]>(
    plan.features
  );

  useEffect(() => {
    const initialComponents: any[] = plan.components.map((component) => {
      return {
        metric: component.billable_metric.billable_metric_name,
        cost_per_batch: component.cost_per_batch,
        metric_units_per_batch: component.metric_units_per_batch,
        free_metric_units: component.free_metric_units,
        max_metric_units: component.max_metric_units,
      };
    });
    console.log(initialComponents);
    setComponentsData(initialComponents);
  }, [plan.components]);

  const mutation = useMutation(
    (data: UpdatePlanType) => Plan.updatePlan(data),
    {
      onSuccess: () => {
        toast.success("Successfully updated Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
        queryClient.invalidateQueries(["plan_list"]);
        navigate("/plans");
      },
      onError: () => {
        toast.error("Failed to update Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const createPlanMutation = useMutation(
    (post: CreatePlanType) => Plan.createPlan(post),
    {
      onSuccess: (res) => {
        if (type == "backtest") {
          setReplacementPlan(res);
        }
        queryClient.invalidateQueries(["plan_list"]);
        form.resetFields();
        navigate("/create-experiment");
      },
      onError: () => {
        toast.error("Failed to create Plan", {
          position: toast.POSITION.TOP_CENTER,
        });
      },
    }
  );

  const addFeatures = (newFeatures: FeatureType[]) => {
    newFeatures.filter((item) => planFeatures.indexOf(item) !== -1);

    setPlanFeatures([...planFeatures, ...newFeatures]);
    setFeatureVisible(false);
  };

  const editFeatures = (feature_name: string) => {
    const currentFeature = planFeatures.filter(
      (item) => item.feature_name === feature_name
    )[0];
    setFeatureVisible(true);
  };

  const removeFeature = (feature_name: string) => {
    setPlanFeatures(
      planFeatures.filter((item) => item.feature_name !== feature_name)
    );
  };

  const onFinishFailed = (errorInfo: any) => {};

  const hideComponentModal = () => {
    setcomponentVisible(false);
  };

  const showComponentModal = () => {
    setcomponentVisible(true);
  };

  const handleComponentAdd = (newData: any) => {
    const old = componentsData;

    if (editComponentItem) {
      const index = componentsData.findIndex(
        (item) => item.id === editComponentItem.id
      );
      old[index] = newData;
      setComponentsData(old);
    } else {
      const newComponentsData = [
        ...old,
        {
          ...newData,
          id: Math.floor(Math.random() * 1000),
        },
      ];
      setComponentsData(newComponentsData);
    }
    setEditComponentsItem(undefined);
    setcomponentVisible(false);
  };

  const handleComponentEdit = (name: string) => {
    const currentComponent = componentsData.filter(
      (item) => item.metric === name
    )[0];

    setEditComponentsItem(currentComponent);
    setcomponentVisible(true);
  };

  const deleteComponent = (name: string) => {
    setComponentsData(componentsData.filter((item) => item.metric !== name));
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
        const components: any = Object.values(componentsData);
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

        const newPlan: CreatePlanType = {
          name: values.name,
          description: values.description,
          flat_rate: values.flat_rate,
          pay_in_advance: values.pay_in_advance,
          interval: values.billing_interval,
          components: usagecomponentslist,
          features: planFeatures,
        };
        if (type === "backtest") {
          newPlan["status"] = "experimental";
          createPlanMutation.mutate(newPlan);
        } else if (type === "edit") {
          mutation.mutate({
            old_billing_plan_id: plan.billing_plan_id,
            updated_billing_plan: newPlan,
            update_behavior: values.update_behavior,
          });
        }
      })
      .catch((info) => {
        console.log("Validate Failed:", info);
      });
  };

  function returnPageTitle(): string {
    if (type === "backtest") {
      return "Backtest Plan";
    } else if (type === "edit") {
      return "Update Plan";
    } else {
      return "Create Plan";
    }
  }

  function returnSubmitButtonText(): string {
    if (type === "backtest") {
      return "Finish Plan";
    } else if (type === "edit") {
      return "Update Plan";
    } else {
      return "Create Plan";
    }
  }

  return (
    <PageLayout
      title={returnPageTitle()}
      extra={[
        <Button
          key={"back"}
          onClick={goBackPage}
          icon={<ArrowLeftOutlined />}
          type="default"
          size="large"
        >
          Back
        </Button>,
        <Button
          key="create"
          onClick={() => form.submit()}
          className="bg-black text-white justify-self-end"
          size="large"
        >
          {returnSubmitButtonText()}
        </Button>,
      ]}
    >
      <Form.Provider>
        <Form
          form={form}
          name="create_plan"
          initialValues={{
            name: plan.name,
            description: plan.description,
            flat_rate: plan.flat_rate,
            pay_in_advance: plan.pay_in_advance,
            billing_interval: plan.interval,
          }}
          onFinish={submitPricingPlan}
          onFinishFailed={onFinishFailed}
          autoComplete="off"
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 16 }}
          labelAlign="left"
        >
          <Row gutter={24}>
            <Col span={12}>
              <Row gutter={[24, 24]}>
                <Col span="24">
                  <Card title="Plan Information">
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
                      <Radio.Group>
                        <Radio value="week">Weekly</Radio>
                        <Radio value="month">Monthly</Radio>
                        <Radio value="year">Yearly</Radio>
                      </Radio.Group>
                    </Form.Item>

                    <Form.Item name="flat_rate" label="Recurring Cost">
                      <InputNumber
                        addonBefore="$"
                        defaultValue={0}
                        precision={2}
                      />
                    </Form.Item>
                    <Form.Item name="pay_in_advance" label="Pay In Advance">
                      <Checkbox defaultChecked={true} />
                    </Form.Item>
                    {type === "edit" && (
                      <Form.Item
                        name="update_behavior"
                        label="When To Update Plan"
                        rules={[
                          {
                            required: true,
                            message: "Please select an update behavior",
                          },
                        ]}
                      >
                        <Radio.Group optionType="button" buttonStyle="solid">
                          <Radio value="replace_immediately">Immediately</Radio>
                          <Radio value="replace_on_renewal">On Renewal</Radio>
                        </Radio.Group>
                      </Form.Item>
                    )}
                  </Card>
                </Col>
                <Col span="24">
                  <Card
                    title="Added Features"
                    extra={[
                      <Button htmlType="button" onClick={showFeatureModal}>
                        Add Feature
                      </Button>,
                    ]}
                  >
                    <Form.Item
                      wrapperCol={{ span: 24 }}
                      shouldUpdate={(prevValues, curValues) =>
                        prevValues.components !== curValues.components
                      }
                    >
                      <Row gutter={[12, 12]}>
                        {planFeatures.map((feature, index) => (
                          <Col key={index} span={24}>
                            <Paper color="gold">
                              <Descriptions
                                title={feature.feature_name}
                                size="small"
                                extra={[
                                  <Button
                                    type="text"
                                    size="small"
                                    icon={<EditOutlined />}
                                    onClick={() =>
                                      editFeatures(feature.feature_name)
                                    }
                                  />,
                                  <Button
                                    type="text"
                                    size="small"
                                    icon={<DeleteOutlined />}
                                    danger
                                    onClick={() =>
                                      removeFeature(feature.feature_name)
                                    }
                                  />,
                                ]}
                              />
                            </Paper>
                          </Col>
                        ))}
                      </Row>
                    </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>

            <Col span={12}>
              <Row gutter={[24, 24]}>
                <Col span={24}>
                  <Card
                    title="Added Components"
                    extra={[
                      <Button
                        htmlType="button"
                        onClick={() => showComponentModal()}
                      >
                        Add Component
                      </Button>,
                    ]}
                  >
                    <Form.Item
                      wrapperCol={{ span: 24 }}
                      shouldUpdate={(prevValues, curValues) =>
                        prevValues.components !== curValues.components
                      }
                    >
                      <Row gutter={[12, 12]}>
                        {componentsData?.map(
                          (component: any, index: number) => (
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
                                      onClick={() =>
                                        handleComponentEdit(component.metric)
                                      }
                                    />,
                                    <Button
                                      key="delete"
                                      type="text"
                                      size="small"
                                      icon={<DeleteOutlined />}
                                      danger
                                      onClick={() =>
                                        deleteComponent(component.metric)
                                      }
                                    />,
                                  ]}
                                >
                                  <Descriptions.Item label="Cost" span={4}>
                                    {component.cost_per_batch
                                      ? `$${component.cost_per_batch} / ${component.metric_units_per_batch} Unit(s)`
                                      : "Free"}
                                  </Descriptions.Item>
                                  <Descriptions.Item
                                    label="Free Units"
                                    span={1}
                                  >
                                    {component.free_amount ?? "Unlimited"}
                                  </Descriptions.Item>
                                  <Descriptions.Item label="Max Units" span={1}>
                                    {component.max_metric_units ?? "Unlimited"}
                                  </Descriptions.Item>
                                </Descriptions>
                              </Paper>
                            </Col>
                          )
                        )}
                      </Row>
                    </Form.Item>
                  </Card>
                </Col>
              </Row>
            </Col>
          </Row>
        </Form>
        {componentVisible && (
          <UsageComponentForm
            visible={componentVisible}
            onCancel={hideComponentModal}
            componentsData={componentsData}
            handleComponentAdd={handleComponentAdd}
            editComponentItem={editComponentItem}
            setEditComponentsItem={setEditComponentsItem}
          />
        )}
        {featureVisible && (
          <FeatureForm
            visible={featureVisible}
            onCancel={hideFeatureModal}
            onAddFeatures={addFeatures}
          />
        )}
      </Form.Provider>
    </PageLayout>
  );
};

export default EditPlan;
