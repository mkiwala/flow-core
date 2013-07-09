angular.module('processMonitor.controllers', ['processMonitor.services', 'angularTree'])
    .controller('MainController', ['$scope', 'statusService',
        function($scope, statusService) {
            // console.log("MainController instantiated.");
            $scope.status_current = statusService.status_current;
            $scope.status_all = statusService.status_all;
            $scope.status_processes = statusService.status_processes;
        }])
    .controller('ProcessTree', ['$scope', 'statusService',
        function($scope, statusService) {
            $scope.test = "testing 1 2 3";
            $scope.processes = statusService.processes;

            $scope.tree_model = [
                {
                    name: 'Item 1 Name',
                    children: [
                        {
                            name: 'Item 2 Name',
                            children: [
                                {
                                    name: 'Item 2A Name'
                                }
                            ]
                        },
                        {
                            name: 'Item 3 Name'
                        }
                    ]
                }
            ];
        }]);
