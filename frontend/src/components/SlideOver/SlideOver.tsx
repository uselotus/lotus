import React from "react";
import useToggleSlideOver from "../../stores/useToggleSlideOver";
import { PlusOutlined, CloseOutlined } from "@ant-design/icons";
import useGlobalStore from "../../stores/useGlobalstore";
import SlideOverCard from "./SlideOverCard";
interface SlideOverProps {}

const SlideOver: React.FC<SlideOverProps> = () => {
  const { linked_organizations } = useGlobalStore((state) => state.org);
  console.log(linked_organizations);
  const open = useToggleSlideOver((state) => state.open);
  const setOpen = useToggleSlideOver((state) => state.setOpen);
  return (
    <div
      className="relative z-20"
      aria-labelledby="slide-over-title"
      role="dialog"
      aria-modal="true"
    >
      <div className="fixed inset-0"></div>
      <div className="fixed inset-0 overflow-hidden">
        <div className="absolute inset-0  overflow-hidden">
          <div className="pointer-events-none fixed inset-y-0 right-[0px] flex max-w-full">
            <div className="pointer-events-auto w-screen h-screen max-w-md">
              <div className="flex h-full flex-col overflow-y-scroll bg-white py-6 shadow-xl">
                <div className="px-4 sm:px-6">
                  <div className="flex items-baseline mt-4">
                    <h2
                      className="text-lg font-medium text-gray-900 font-arimo"
                      id="slide-over-title"
                    >
                      Account Environments
                    </h2>
                    <div className="ml-auto flex flex-row  items-center ">
                      <PlusOutlined className="!text-gold w-12 h-12 cursor-pointer" />
                      <CloseOutlined className="w-12 h-12 cursor-pointer" />
                    </div>
                  </div>
                  <div className=" w-full h-[1.5px] mt-2 bg-card-divider" />
                </div>
                <div className="relative mt-6 flex-1 px-4 sm:px-6">
                  {/* replace w your content */}
                  <SlideOverCard />
                  <div className="absolute inset-0 px-4 sm:px-6">
                    <div
                      className="h-full border-2 border-dashed border-gray-200"
                      aria-hidden="true"
                    ></div>
                  </div>
                  {/* end replace */}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SlideOver;
